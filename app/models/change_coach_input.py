# coding: utf-8

"""
    FutBot API

    API REST para la plataforma FutBot:\\ Gestion de usuarios, jugadores, partidos, ligas, comportamientos en Python y datos del ranking
    
    Do not edit the class manually.
"""  # noqa: E501


from __future__ import annotations
import pprint
import re  # noqa: F401
import json


from pydantic import BaseModel, StrictStr
from typing import Any, ClassVar, Dict, List, Optional
from uuid import UUID
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class ChangeCoachInput(BaseModel):
    """
    ChangeCoachInput
    """  # noqa: E501
    behavior_id: Optional[UUID]
    __properties: ClassVar[List[str]] = ["behavior_id"]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }

    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance of ChangeCoachInput from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias.

        Se incluye behavior_id aunque sea None, porque null es un valor
        valido (significa "quitar el DT").
        """
        _dict = self.model_dump(
            by_alias=True,
            exclude={},
            exclude_none=False,
        )
        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of ChangeCoachInput from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "behavior_id": obj.get("behavior_id")
        })
        return _obj