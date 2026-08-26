from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app import crud
from app.models import Category


def _integrity_error() -> IntegrityError:
    return IntegrityError("statement", {}, Exception("constraint violation"))


def test_list_and_get_items_delegate_to_session():
    db = MagicMock()
    db.scalars.return_value.all.return_value = ["first", "second"]

    assert crud.list_items(db, Category, offset=2, limit=3) == ["first", "second"]
    db.scalars.assert_called_once()

    db.get.return_value = "item"
    assert crud.get_item(db, Category, 7) == "item"
    db.get.assert_called_once_with(Category, 7)


def test_create_item_commits_and_refreshes():
    db = MagicMock()
    obj = MagicMock()

    assert crud.create_item(db, obj) is obj
    db.add.assert_called_once_with(obj)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(obj)


def test_create_item_can_defer_commit_for_atomic_audit_write():
    db = MagicMock()
    obj = MagicMock()

    assert crud.create_item(db, obj, commit=False) is obj
    db.add.assert_called_once_with(obj)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.refresh.assert_called_once_with(obj)


def test_create_item_rolls_back_integrity_error():
    db = MagicMock()
    db.commit.side_effect = _integrity_error()

    with pytest.raises(ValueError, match="Não foi possível criar o registro"):
        crud.create_item(db, MagicMock())

    db.rollback.assert_called_once_with()


def test_delete_item_commits():
    db = MagicMock()
    obj = MagicMock()

    crud.delete_item(db, obj)

    db.delete.assert_called_once_with(obj)
    db.commit.assert_called_once_with()


def test_delete_item_can_defer_commit():
    db = MagicMock()
    obj = MagicMock()

    crud.delete_item(db, obj, commit=False)

    db.delete.assert_called_once_with(obj)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_delete_item_rolls_back_integrity_error():
    db = MagicMock()
    db.commit.side_effect = _integrity_error()

    with pytest.raises(ValueError, match="Não foi possível excluir o registro"):
        crud.delete_item(db, MagicMock())

    db.rollback.assert_called_once_with()


def test_update_item_applies_changes_commits_and_refreshes():
    db = MagicMock()

    class Item:
        name = "old"
        active = False

    obj = Item()

    assert crud.update_item(db, obj, {"name": "new", "active": True}) is obj
    assert obj.name == "new"
    assert obj.active is True
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(obj)


def test_update_item_can_defer_commit():
    db = MagicMock()

    class Item:
        name = "old"

    obj = Item()
    assert crud.update_item(db, obj, {"name": "new"}, commit=False) is obj
    assert obj.name == "new"
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.refresh.assert_called_once_with(obj)


def test_update_item_rolls_back_integrity_error():
    db = MagicMock()
    db.commit.side_effect = _integrity_error()

    class Item:
        name = "old"

    obj = Item()

    with pytest.raises(ValueError, match="Não foi possível atualizar o registro"):
        crud.update_item(db, obj, {"name": "new"})

    assert obj.name == "new"
    db.rollback.assert_called_once_with()
