import pytest

from ytps.config import Config, Tier, Visibility
from ytps.errors import CredentialsRequired


def test_public_read_needs_nothing():
    assert Config().resolve_tier("fetch", Visibility.PUBLIC) is Tier.NONE


def test_unlisted_read_needs_nothing():
    assert Config().resolve_tier("fetch", "unlisted") is Tier.NONE


def test_private_read_demands_oauth_and_says_why():
    with pytest.raises(CredentialsRequired) as e:
        Config().resolve_tier("fetch", Visibility.PRIVATE)
    msg = str(e.value)
    assert "YT_OAUTH_CLIENT_ID" in msg
    assert "Unlisted" in msg  # offers the cheaper way out


def test_private_read_ok_with_oauth():
    cfg = Config(client_id="id", client_secret="secret")
    assert cfg.resolve_tier("fetch", Visibility.PRIVATE) is Tier.OAUTH


def test_api_key_cannot_substitute_for_oauth():
    cfg = Config(api_key="key")
    with pytest.raises(CredentialsRequired):
        cfg.resolve_tier("create", Visibility.PUBLIC)


@pytest.mark.parametrize("op", ["create", "edit", "delete", "publish"])
def test_every_write_needs_oauth(op):
    with pytest.raises(CredentialsRequired):
        Config().resolve_tier(op, Visibility.PUBLIC)
    assert Config(client_id="i", client_secret="s").resolve_tier(op) is Tier.OAUTH


def test_prefer_api_only_applies_with_a_key():
    assert Config(prefer_api_for_reads=True).resolve_tier("fetch") is Tier.NONE
    assert Config(prefer_api_for_reads=True, api_key="k").resolve_tier("fetch") is Tier.API_KEY


def test_unknown_operation_rejected():
    with pytest.raises(ValueError):
        Config().resolve_tier("frobnicate")
