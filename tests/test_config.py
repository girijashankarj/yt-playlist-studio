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


def test_blank_env_values_fall_back_to_defaults(monkeypatch):
    # .env.example ships blank values; a copied .env must not crash every command
    for var in ("YT_OAUTH_PORT", "YTPS_DAILY_QUOTA", "YT_OAUTH_TOKEN_PATH",
                "YTPS_STATE_DIR", "YTPS_OUTPUT_DIR"):
        monkeypatch.setenv(var, "")
    cfg = Config.load(env_file=None)
    assert cfg.oauth_port == 0
    assert cfg.daily_quota == 10_000
    assert str(cfg.token_path) == ".tokens/token.json"
    assert str(cfg.state_dir) == ".ytps"


def test_whitespace_only_env_value_is_treated_as_blank(monkeypatch):
    monkeypatch.setenv("YT_OAUTH_PORT", "   ")
    assert Config.load(env_file=None).oauth_port == 0


def test_numeric_env_values_are_read(monkeypatch):
    monkeypatch.setenv("YT_OAUTH_PORT", "8080")
    monkeypatch.setenv("YTPS_DAILY_QUOTA", "50000")
    cfg = Config.load(env_file=None)
    assert cfg.oauth_port == 8080 and cfg.daily_quota == 50_000


def test_non_numeric_env_value_says_what_was_wrong(monkeypatch):
    monkeypatch.setenv("YT_OAUTH_PORT", "eighty-eighty")
    with pytest.raises(ValueError, match="expected a number"):
        Config.load(env_file=None)


def test_mask_never_reveals_a_whole_secret():
    from ytps.auth import mask

    secret = "GOCSPX-SuperSecretValueHere12345"
    out = mask(secret)
    assert secret not in out and "…" in out
    assert mask(None) == "(not set)"


def test_check_rejects_the_shipped_placeholders():
    from ytps.auth import check_credentials

    cfg = Config(
        client_id="123456789012-REPLACE_WITH_YOUR_CLIENT_ID.apps.googleusercontent.com",
        client_secret="GOCSPX-ReplaceThisWithYourRealSecret",
    )
    r = check_credentials(cfg)
    assert not r["ready"]
    assert any("placeholder" in p for p in r["problems"])


def test_check_catches_swapped_id_and_secret():
    from ytps.auth import check_credentials

    cid = "99887766-realish.apps.googleusercontent.com"
    r = check_credentials(Config(client_id=cid, client_secret=cid))
    assert not r["ready"]
    assert any("swapped" in p for p in r["problems"])


def test_check_passes_on_well_formed_credentials():
    from ytps.auth import check_credentials

    r = check_credentials(
        Config(client_id="99887766-realish.apps.googleusercontent.com",
               client_secret="GOCSPX-aRealLookingSecret")
    )
    assert r["ready"] and not r["problems"]
