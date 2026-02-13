"""Tests for Django model field relationship extractor."""

from __future__ import annotations

import pytest

from clew.chunker.parser import ASTParser
from clew.indexer.extractors.django_models import DjangoModelFieldExtractor


@pytest.fixture
def extractor() -> DjangoModelFieldExtractor:
    return DjangoModelFieldExtractor()


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


class TestDjangoModelFieldExtractor:
    def test_foreign_key_extraction(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        source = """
class Order(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert len(rels) == 1
        assert rels[0].relationship == "has_fk"
        assert rels[0].source_entity == "app/models.py::Order"
        assert rels[0].target_entity == "User"

    def test_many_to_many_extraction(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        source = """
class Article(models.Model):
    tags = models.ManyToManyField("Tag")
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "blog/models.py")
        assert len(rels) == 1
        assert rels[0].relationship == "has_m2m"
        assert rels[0].target_entity == "Tag"

    def test_one_to_one_extraction(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        source = """
class Profile(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "accounts/models.py")
        assert len(rels) == 1
        assert rels[0].relationship == "has_o2o"
        assert rels[0].target_entity == "User"

    def test_self_referential_foreign_key(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        source = """
class Category(models.Model):
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "shop/models.py")
        assert len(rels) == 1
        assert rels[0].relationship == "has_fk"
        assert rels[0].target_entity == "Category"

    def test_non_model_class_ignored(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        source = """
class NotAModel:
    field = models.ForeignKey("User", on_delete=models.CASCADE)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert len(rels) == 0

    def test_multiple_fields_in_one_model(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        source = """
class Order(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    products = models.ManyToManyField("Product")
    shipping = models.OneToOneField("Address", on_delete=models.SET_NULL, null=True)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "ecomm/models.py")
        assert len(rels) == 3
        rel_types = {r.relationship for r in rels}
        assert rel_types == {"has_fk", "has_m2m", "has_o2o"}

    def test_model_inheriting_from_abstract_model(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        """Classes inheriting from *Model base classes are detected."""
        source = """
class TimestampedOrder(TimeStampedModel):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert len(rels) == 1
        assert rels[0].relationship == "has_fk"

    def test_bare_field_name_without_models_prefix(
        self, extractor: DjangoModelFieldExtractor, parser: ASTParser
    ) -> None:
        """ForeignKey without models. prefix is also extracted."""
        source = """
from django.db.models import ForeignKey

class Order(models.Model):
    user = ForeignKey("User", on_delete=models.CASCADE)
"""
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert len(rels) == 1
        assert rels[0].relationship == "has_fk"
