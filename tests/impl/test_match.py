import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.engine.constants import TRIANGLE_HOME
from app.engine.executor import BehaviorExecutor
from app.engine.state import MatchState, Side
from app.security.tokens import create_access_token
from app.ws.match.info import ClubSummary, MatchInfo
from app.ws.match.runner import LiveMatch, live_matches, match_connections, Phase
from tests.engine.conftest import make_player
from tests.ws.match.conftest import lineup_player

ON_FIELD = str(uuid.uuid4())
ON_BENCH = str(uuid.uuid4())


@pytest.fixture
async def club(session):
    """Usuario, club y un comportamiento de jugador reales en la base de test."""
    user = UserDB(email="hola@prueba.com", hashed_password="hash")
    session.add(user)
    await session.flush()
    club = ClubDB(club_name="Instituto", avatar_url="https://x/c.png", user_id=user.id)
    session.add(club)
    await session.flush()
    behavior = BehaviorDB(
        name="Atacante", code="def decide_action(): pass", club_id=club.id
    )
    session.add(behavior)
    await session.commit()
    return club, behavior


@pytest.fixture
def live(club):
    """Partido en juego del club (local): un titular en cancha y un suplente."""
    home_id, away_id = str(club[0].id), str(uuid.uuid4())
    state = MatchState(
        home_team_id=home_id,
        home_formation=TRIANGLE_HOME,
        away_team_id=away_id,
        away_formation=TRIANGLE_HOME,
        players=[make_player(ON_FIELD, Side.HOME)],
        total_ticks=3000,
    )
    info = MatchInfo(
        home_club=ClubSummary(id=home_id, name="Local", avatar_url="https://x/l.png"),
        away_club=ClubSummary(id=away_id, name="Visita", avatar_url="https://x/v.png"),
        home_lineup=[
            lineup_player(ON_FIELD, 1, True),
            lineup_player(ON_BENCH, 2, False),
        ],
        away_lineup=[],
    )
    live = LiveMatch(
        match_id=uuid.uuid4(),
        state=state,
        executor=BehaviorExecutor(state, {}),
        info=info,
        match_start=datetime.now(timezone.utc),
    )
    live_matches[live.match_id] = live
    yield live
    live_matches.pop(live.match_id, None)


def auth_header(club) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(club[0].user_id)}"}


def url(match_id) -> str:
    return f"/matches/{match_id}/substitutions"


def body(club, player_in=ON_BENCH) -> dict:
    return {
        "player_out_id": ON_FIELD,
        "player_in_id": player_in,
        "substitution_behavior_id": str(club[1].id),
    }


async def test_post_schedules_the_substitution(client, club, live):
    result = await client.post(
        url(live.match_id), json=body(club), headers=auth_header(club)
    )

    assert result.status_code == 201
    assert result.json()["status"] == "pending"
    assert result.json()["window"] == "cooling_break_1"
    assert str(club[0].id) in live.pending_substitutions


async def test_post_400_if_the_player_in_is_not_on_the_bench(client, club, live):
    result = await client.post(
        url(live.match_id),
        json=body(club, player_in=ON_FIELD),
        headers=auth_header(club),
    )

    assert result.status_code == 400
    assert live.pending_substitutions == {}


async def test_post_403_if_the_club_does_not_play_the_match(client, club, live):
    live.info.home_club.id = str(uuid.uuid4())

    result = await client.post(
        url(live.match_id), json=body(club), headers=auth_header(club)
    )

    assert result.status_code == 403


async def test_post_404_if_the_match_is_not_being_played(client, club):
    result = await client.post(url(uuid.uuid4()), json=body(club), headers=auth_header(club))

    assert result.status_code == 404


async def test_post_409_if_there_is_already_one_pending(client, club, live):
    await client.post(url(live.match_id), json=body(club), headers=auth_header(club))

    result = await client.post(
        url(live.match_id), json=body(club), headers=auth_header(club)
    )

    assert result.status_code == 409


async def test_delete_cancels_the_pending_substitution(client, club, live):
    await client.post(url(live.match_id), json=body(club), headers=auth_header(club))

    result = await client.delete(url(live.match_id), headers=auth_header(club))

    assert result.status_code == 200
    assert live.pending_substitutions == {}


async def test_delete_404_if_there_is_no_pending_one(client, club, live):
    result = await client.delete(url(live.match_id), headers=auth_header(club))

    assert result.status_code == 404

def behavior_url(match_id, player_id) -> str:
    return f"/matches/{match_id}/players/{player_id}"  #para no escribir la url a mano en todos lso tests


@pytest.fixture
def sent(monkeypatch):   #sirve para ver que mensakes manda el endpoint por websocket sin abir un ws real.
    messages = []

    async def fake_broadcast(channel_id, message): #en vez de mandar el msj a los clientes, lo manda a la lista vacia mesasges.
        messages.append((channel_id, message))

    monkeypatch.setattr(match_connections, "broadcast", fake_broadcast) #reemplazo el metodo.
    return messages


@pytest.fixture
def behavior_calls(live, monkeypatch):
    """Registra las llamadas a executor.set_behavior sin mandar nada al proceso hijo.
    Que el executor aplique bien el cambio ya se testea en tests/engine/test_executor.py."""
    calls = []

    def fake_set_behavior(player_id, code):
        calls.append((player_id, code))

    monkeypatch.setattr(live.executor, "set_behavior", fake_set_behavior)
    return calls


async def test_changes_live_behavior(client, club, live, sent, behavior_calls):
    #club crea una tupla (club, behavior)
    #client para simular las consultas quue hace el front
    #live arma un partido en vivo y lo registra el live_matches
    #behavior_calls guarda con que (player_id, code) se llamo a executor.set_behavior

    behavior = club[1]

    result = await client.patch(
        behavior_url(live.match_id, ON_FIELD), 
        json={"behavior_id": str(behavior.id)},
        headers=auth_header(club),
    )  # LO que pide el router (de la URL se extrae el match_id y el player_id, del body el ChangeLiveBehaviorRequest y del header(token) el club)

    assert result.status_code == 200
    assert behavior_calls == [(ON_FIELD, behavior.code)] #chequeo que se le pidio al executor cargar el comportamiento

    player = next(p for p in live.info.home_lineup if p.player_id == ON_FIELD)
    assert player.behavior_id == str(behavior.id) #veo que se actualizo la info
    assert player.behavior_name == behavior.name

    assert len(sent) == 1 #veo que se mando el mensaje
    channel_id, message = sent[0]
    assert channel_id == live.match_id #veo que se haya mandado bien
    assert message["type"] == "behaviorChanged"
    assert message["data"] == {
        "match_id": str(live.match_id),
        "tick": live.state.tick,
        "player_id": ON_FIELD,
        "behavior_id": str(behavior.id),
        "behavior_name": behavior.name,
    }

async def test_changes_live_behavior_match_penalties(client, club, live, sent):
    live.phase = Phase.PENALTIES

    behavior = club[1]

    result = await client.patch(
        behavior_url(live.match_id, ON_FIELD),
        json={"behavior_id": str(behavior.id)},
        headers=auth_header(club),
    )
    assert len(sent) == 0 #chuqeo q no se mande nada
    assert result.status_code == 409
    assert result.json()["message"] == "El partido se encuentra en penales"  #LA excepcion la agarra FastApi y la convierte a un mensaje HTTP

async def test_change_live_behavior_match_no_init(client, club, sent):
    behavior = club [1]

    result = await client.patch(
        behavior_url(uuid.uuid4(), ON_FIELD),
        json={"behavior_id": str(behavior.id)},
        headers=auth_header(club),
    )

    assert len(sent) == 0 #chuqeo q no se mande nada
    assert result.status_code == 404
    assert result.json()["message"] == "El partido no está en juego"

async def test_changes_live_behavior_club_not_match(client, club, live, sent):
    live.info.home_club.id = str(uuid.uuid4())
    behavior = club[1]

    result = await client.patch(
        behavior_url(live.match_id, ON_FIELD),
        json={"behavior_id": str(behavior.id)},
        headers=auth_header(club),
    )
    assert len(sent) == 0 #chuqeo q no se mande nada
    assert result.status_code == 403
    assert result.json()["message"] == "El club no juega este partido"

async def test_changes_live_behavior_behavior_not_exist(client, club, live, sent):

    result = await client.patch(
        behavior_url(live.match_id, ON_FIELD),
        json={"behavior_id": str(uuid.uuid4())},
        headers=auth_header(club),
    )
    assert len(sent) == 0 #chuqeo q no se mande nada
    assert result.status_code == 400
    assert result.json()["message"] == "El comportamiento no existe"

async def test_change_live_behavior_player_not_field(client, club, live, sent, behavior_calls):
    behavior = club[1]

    result = await client.patch(
        behavior_url(live.match_id, ON_BENCH),
        json={"behavior_id": str(behavior.id)},
        headers=auth_header(club),
    )

    assert len(sent) == 0  # chequeo que no se mande nada
    assert behavior_calls == []  # no se le aplicó el comportamiento
    assert result.status_code == 404
    assert (result.json()["message"] == "El jugador no se encuentra en cancha del lado del club"
)


# --- PUT /matches/{match_id}/penalty-order ---
SQUAD = [ON_FIELD, ON_BENCH, *(str(uuid.uuid4()) for _ in range(4))]


@pytest.fixture
def penalty_window(live):
    """La ventana de penales abierta, con los 6 convocados del local."""
    live.info.home_lineup = [
        lineup_player(player_id, n, n <= 3) for n, player_id in enumerate(SQUAD, start=1)
    ]
    live.phase = Phase.PENALTIES
    return live


@pytest.fixture
def penalty_behavior_calls(live, monkeypatch):
    """Registra las llamadas a executor.set_player_behavior sin mandar nada al hijo."""
    calls = []

    def fake_set_player_behavior(player, code):
        calls.append((player.id, code))

    monkeypatch.setattr(live.executor, "set_player_behavior", fake_set_player_behavior)
    return calls


def penalty_url(match_id) -> str:
    return f"/matches/{match_id}/penalty-order"


def penalty_body(club, player_ids=SQUAD[:5], behavior_id=None) -> dict:
    behavior_id = behavior_id or str(club[1].id)
    return {
        "kickers": [{"player_id": p, "behavior_id": behavior_id} for p in player_ids]
    }


async def test_put_penalty_order_saves_it_and_loads_the_behaviors(
    client, club, penalty_window, penalty_behavior_calls
):
    order = [SQUAD[5], SQUAD[4], SQUAD[0], SQUAD[1], SQUAD[2]]  # con dos suplentes

    result = await client.put(
        penalty_url(penalty_window.match_id),
        json=penalty_body(club, order),
        headers=auth_header(club),
    )

    assert result.status_code == 200
    kickers = penalty_window.penalty_orders[str(club[0].id)]
    assert [k.id for k in kickers] == order
    assert all(k.side == Side.HOME for k in kickers)
    assert penalty_behavior_calls == [(p, club[1].code) for p in order]


@pytest.mark.parametrize(
    "player_ids",
    [
        SQUAD[:4],  # no son 5
        [SQUAD[0], SQUAD[0], SQUAD[1], SQUAD[2], SQUAD[3]],  # repetidos
        [*SQUAD[:4], str(uuid.uuid4())],  # uno no es convocado
    ],
)
async def test_put_penalty_order_400_if_the_kickers_are_wrong(
    client, club, penalty_window, penalty_behavior_calls, player_ids
):
    result = await client.put(
        penalty_url(penalty_window.match_id),
        json=penalty_body(club, player_ids),
        headers=auth_header(club),
    )

    assert result.status_code == 400
    assert penalty_window.penalty_orders == {}
    assert penalty_behavior_calls == []


@pytest.mark.parametrize("kind", ["ajeno", "coach"])
async def test_put_penalty_order_400_if_a_behavior_is_not_own_or_is_of_coach(
    client, club, session, penalty_window, penalty_behavior_calls, kind
):
    behavior_id = str(uuid.uuid4())  # no existe, o es de otro club
    if kind == "coach":
        coach = BehaviorDB(
            name="DT", code="def decide_coach(): pass", club_id=club[0].id, kind="coach"
        )
        session.add(coach)
        await session.commit()
        behavior_id = str(coach.id)

    result = await client.put(
        penalty_url(penalty_window.match_id),
        json=penalty_body(club, behavior_id=behavior_id),
        headers=auth_header(club),
    )

    assert result.status_code == 400
    assert penalty_window.penalty_orders == {}
    assert penalty_behavior_calls == []  # no cargó ninguno a medias


async def test_put_penalty_order_409_if_there_is_no_window(client, club, live):
    result = await client.put(
        penalty_url(live.match_id), json=penalty_body(club), headers=auth_header(club)
    )

    assert result.status_code == 409


async def test_put_penalty_order_409_once_the_shootout_started(
    client, club, penalty_window
):
    penalty_window.shootout = object()  # ya arrancó la tanda

    result = await client.put(
        penalty_url(penalty_window.match_id),
        json=penalty_body(club),
        headers=auth_header(club),
    )

    assert result.status_code == 409


async def test_put_penalty_order_403_if_the_club_does_not_play(
    client, club, penalty_window
):
    penalty_window.info.home_club.id = str(uuid.uuid4())

    result = await client.put(
        penalty_url(penalty_window.match_id),
        json=penalty_body(club),
        headers=auth_header(club),
    )

    assert result.status_code == 403


async def test_put_penalty_order_404_if_the_match_is_not_being_played(client, club):
    result = await client.put(
        penalty_url(uuid.uuid4()), json=penalty_body(club), headers=auth_header(club)
    )

    assert result.status_code == 404
