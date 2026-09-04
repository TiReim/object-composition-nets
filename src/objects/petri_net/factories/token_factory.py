from typing import TypeVar

from src.objects.data_types.object_reference import Identity
from src.objects.petri_net.place import Place
from src.objects.petri_net.token import IdentityToken, Token

# pylint: disable=invalid-name, too-few-public-methods

P = TypeVar("P", bound=Place)
TO = TypeVar("TO", bound=Token)


class TokenFactory:
    @staticmethod
    def create_token(place: P, identity: Identity) -> Token:
        return IdentityToken(place, identity) if identity is not None else place
