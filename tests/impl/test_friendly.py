import uuid

import pytest
from fastapi import HTTPException

from app.impl.friendlies_api_impl import _validate_squad
from app.models.squad_player_input import SquadPlayerInput

CANT_JUGADORES = 6

def make_squad( starters : int, total : int = CANT_JUGADORES) -> list[SquadPlayerInput]:
    return[
        SquadPlayerInput(
            player_id= uuid.uuid4(),
            is_starter= rango < starters,
            behavior_id=uuid.uuid4() if rango < starters else None
        )
        for rango in range(total)
    ]

def test_validate_squad_accept_3_tit_and_3_sust():
    assert _validate_squad(make_squad(starters=3)) is None   #si pasa validate_squad retorna None, sino lanza un assert


@pytest.mark.parametrize("starters", [0,1,2,4,5,6])
def test_validate_squad_error_titulares(starters):
    with pytest.raises(HTTPException) as exc_info:
        _validate_squad(make_squad(starters= starters))
    assert exc_info.value.status_code == 400


#def test_validate_squad_error_1_titulares():
#    with pytest.raises(HTTPException) as exc_info:
#        _validate_squad(make_squad(starters=1))
#    assert exc_info.value.status_code == 400

#test con 3 titulares y < 3 suplentes, no se puede porque no se puede armar un amistoso directamente. Ademas no lo chequearia