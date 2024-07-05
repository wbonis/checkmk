#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# pylint: disable=protected-access

import binascii
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

import cmk.utils.paths
from cmk.utils import password_store
from cmk.utils.crypto.secrets import PasswordStoreSecret
from cmk.utils.password_store import PasswordId, PasswordStore

from cmk.ccc.exceptions import MKGeneralException

PW_STORE = "pw_from_store"
PW_EXPL = "pw_explicit"
PW_STORE_KEY = "from_store"


@pytest.fixture(name="fixed_secret")
def fixture_fixed_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Write a fixed value to a tmp file and use that file for the password store secret

    we need the old value since other tests rely on the general path mocking"""
    secret = b"password-secret"
    secret_path = tmp_path / "password_store_fixed.secret"
    secret_path.write_bytes(secret)
    monkeypatch.setattr(PasswordStoreSecret, "path", secret_path)


def test_save(tmp_path: Path) -> None:
    file = tmp_path / "password_store"
    assert not password_store.load(file)
    password_store.save(data := {"ding": "blablu"}, file)
    assert password_store.load(file) == data


def load_patch(_file_path: Path) -> dict[str, str]:
    return {PW_STORE_KEY: PW_STORE}


@pytest.mark.parametrize(
    "password_id, password_actual",
    [
        (("password", PW_EXPL), PW_EXPL),
        (("store", PW_STORE_KEY), PW_STORE),
        (PW_STORE_KEY, PW_STORE),
    ],
)
def test_extract(
    monkeypatch: pytest.MonkeyPatch,
    password_id: PasswordId,
    password_actual: str,
) -> None:
    monkeypatch.setattr(password_store._pwstore, "load", load_patch)
    assert password_store.extract(password_id) == password_actual


def test_extract_from_unknown_valuespec() -> None:
    password_id = ("unknown", "unknown_pw")
    with pytest.raises(MKGeneralException) as excinfo:
        # We test for an invalid structure here
        password_store.extract(password_id)  # type: ignore[arg-type]
    assert "Unknown password type." in str(excinfo.value)


def test_obfuscation() -> None:
    obfuscated = PasswordStore.encrypt(secret := "$ecret")
    assert (
        int.from_bytes(
            obfuscated[: PasswordStore.VERSION_BYTE_LENGTH],
            byteorder="big",
        )
        == PasswordStore.VERSION
    )
    assert PasswordStore.decrypt(obfuscated) == secret


def test_obfuscate_with_own_secret() -> None:
    obfuscated = PasswordStore.encrypt(secret := "$ecret")
    assert PasswordStore.decrypt(obfuscated) == secret

    # The user may want to write some arbritary secret to the file.
    cmk.utils.paths.password_store_secret_file.write_bytes(b"this_will_be_pretty_secure_now.not.")

    # Old should not be decryptable anymore
    with pytest.raises(InvalidTag):
        assert PasswordStore.decrypt(obfuscated)

    # Test encryption and decryption with new key
    assert PasswordStore.decrypt(PasswordStore.encrypt(secret)) == secret


def test_encrypt_decrypt_identity() -> None:
    data = "some random data to be encrypted"
    assert PasswordStore.decrypt(PasswordStore.encrypt(data)) == data


@pytest.mark.usefixtures("fixed_secret")
def test_pw_store_characterization() -> None:
    """This is a characterization (aka "golden master") test to ensure that the password store can
    still decrypt passwords it encrypted before.

    This can only work if the local secret is fixed of course, but a change in the container format,
    the key generation, or algorithms used would be detected.
    """
    # generated by PasswordStore._obfuscate as of commit 79900beda42310dfea9f5bd704041f4e10936ba8
    encrypted = binascii.unhexlify(
        b"00003b1cedb92526621483f9ba140fbe"
        b"55f49916ae77a11a2ac93b4db0758061"
        b"71a62a8aedd3d1edd67e558385a98efe"
        b"be3c4c0ca364e54ff6ad2fa7ef48a0e8"
        b"8ed989283e9604e07da89301658f0370"
        b"d35bba1a8abf74bc971975"
    )

    assert PasswordStore.decrypt(encrypted) == "Time is an illusion. Lunchtime doubly so."
