import pytest

from skillc.formula import (FormulaError, atoms, numeric_vars, validate_expr,
                            validate_formula)


class TestValidateFormula:
    @pytest.mark.parametrize("f", [
        True, False, "pred",
        {"and": ["a", "b"]},
        {"or": ["a", {"not": "b"}]},
        {"not": {"and": ["a", True]}},
        {"cmp": ["price", "<", 500]},
        {"cmp": [{"+": ["x", 1]}, ">=", {"*": [2, "y"]}]},
        {"and": []},
    ])
    def test_accepts(self, f):
        validate_formula(f)

    @pytest.mark.parametrize("f", [
        None, 42, [],
        {"xor": ["a", "b"]},
        {"cmp": ["a", "<>", "b"]},
        {"cmp": ["a", "<"]},
        {"not": None},
        {"and": ["a", 42]},
    ])
    def test_rejects(self, f):
        with pytest.raises(FormulaError):
            validate_formula(f)


class TestValidateExpr:
    @pytest.mark.parametrize("e", [0, -3, "v", {"+": ["a", 1]},
                                   {"-": [{"*": [2, "x"]}, "y"]}])
    def test_accepts(self, e):
        validate_expr(e)

    @pytest.mark.parametrize("e", [True, None, {"+": ["a"]}, {"/": [1, 2]}, 1.5])
    def test_rejects(self, e):
        with pytest.raises(FormulaError):
            validate_expr(e)


def test_atoms():
    f = {"and": ["a", {"or": ["b", {"not": "c"}]}, {"cmp": ["x", "<", 1]}]}
    assert atoms(f) == {"a", "b", "c"}


def test_numeric_vars():
    f = {"and": ["a", {"cmp": [{"+": ["x", "y"]}, "<", "z"]}]}
    assert numeric_vars(f) == {"x", "y", "z"}
