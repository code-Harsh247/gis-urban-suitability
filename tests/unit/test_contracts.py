"""Contract tests (docs/execution_plan.md §4): stub and real files must match schema.py."""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import load_config
from src.features import schema

# ---------------------------------------------------------------- schema itself


def test_model_inputs_exclude_own_cell_and_leaky():
    assert not set(schema.MODEL_INPUTS) & set(schema.OWN_CELL_FEATURES)
    assert not set(schema.MODEL_INPUTS) & set(schema.LEAKY_FEATURES)
    assert set(schema.LEAKY_FEATURES) <= set(schema.OWN_CELL_FEATURES)


def test_feature_names_unique_and_covered_by_c4():
    names = [f for g in schema.FEATURE_GROUPS.values() for f in g]
    assert len(names) == len(set(names)), "a feature is in two groups"
    assert set(names) <= set(schema.CONTRACTS["C4"].columns)


def test_ablation_groups_partition_model_inputs():
    grouped = [f for g in schema.ABLATION_GROUPS for f in schema.FEATURE_GROUPS[g]]
    assert sorted(grouped) == sorted(schema.MODEL_INPUTS)


@pytest.mark.parametrize("bad", ["frac_built", "frac_tree", "bldg_count", "not_a_feature"])
def test_check_model_inputs_rejects(bad):
    with pytest.raises(schema.ContractError):
        schema.check_model_inputs(["ring500_built", bad])


def test_check_model_inputs_accepts_all_model_inputs():
    schema.check_model_inputs(schema.MODEL_INPUTS)


# ---------------------------------------------------------------- stub files


def test_every_contract_has_a_stub(synthetic_project):
    checked = schema.validate_project(synthetic_project)
    assert set(checked) == set(schema.CONTRACTS)


def test_stub_paths_follow_config(synthetic_project):
    years = synthetic_project["years"]
    for year in (years["baseline"], years["latest"]):
        assert schema.contract_path(synthetic_project, "C4", year=year).exists()
    for snap in ("2018", "current"):
        assert schema.contract_path(synthetic_project, "C3", snapshot=snap).exists()
        assert schema.contract_path(synthetic_project, "C6", snapshot=snap).exists()


def test_stub_fractions_sum_to_one(synthetic_project):
    df = pd.read_parquet(
        schema.contract_path(synthetic_project, "C2", year=synthetic_project["years"]["baseline"])
    )
    assert (df[list(schema.OWN_FRACTIONS)].sum(axis=1) - 1).abs().max() < 1e-9


def test_stub_labels_are_usable(synthetic_project):
    lab = pd.read_parquet(schema.contract_path(synthetic_project, "C5"))
    assert lab["grew"].sum() > 5 and lab["chg_train_pos"].sum() > 0
    assert not (lab["grew"] & ~lab["candidate"]).any()
    assert not (lab["candidate"] & lab["excluded"]).any()
    assert set(lab.loc[lab["grew"], "lei_type"]) <= {"adjacent", "outlying"}
    assert (lab.loc[~lab["grew"], "lei_type"] == "none").all()


def test_stub_distance_baseline_beats_random(synthetic_project):
    """The stub city is coherent: nearness to built-up predicts growth."""
    from sklearn.metrics import roc_auc_score

    lab = pd.read_parquet(schema.contract_path(synthetic_project, "C5"))
    cand = lab[lab["candidate"]]
    for model, lo, hi in (("dist_built", 0.7, 1.0), ("random", 0.0, 1.0)):
        s = pd.read_parquet(schema.contract_path(synthetic_project, "C8", model=model))
        m = cand.merge(s, on="cell_id")
        auc = roc_auc_score(m["grew"], m["score"])
        assert lo <= auc <= hi, (model, auc)


# ---------------------------------------------------------------- validator catches errors


@pytest.fixture
def c5(synthetic_project):
    return pd.read_parquet(schema.contract_path(synthetic_project, "C5"))


def test_validator_missing_column(c5):
    with pytest.raises(schema.ContractError, match="missing columns"):
        schema.validate_frame(c5.drop(columns="grew"), "C5")


def test_validator_wrong_dtype(c5):
    with pytest.raises(schema.ContractError, match="dtype"):
        schema.validate_frame(c5.assign(grew=c5["grew"].astype(int)), "C5")


def test_validator_bad_category(c5):
    with pytest.raises(schema.ContractError, match="unexpected values"):
        schema.validate_frame(c5.assign(lei_type="leapfrog"), "C5")


def test_validator_duplicate_key(c5):
    with pytest.raises(schema.ContractError, match="duplicates"):
        schema.validate_frame(pd.concat([c5, c5.head(1)]), "C5")


def test_validator_range(synthetic_project):
    df = pd.read_parquet(schema.contract_path(synthetic_project, "C1"))
    df = df.merge(
        pd.read_parquet(
            schema.contract_path(
                synthetic_project, "C2", year=synthetic_project["years"]["baseline"]
            )
        ),
        on="cell_id",
    )
    bad = df.assign(slope_mean=95.0)
    with pytest.raises(schema.ContractError, match="slope_mean"):
        schema.validate_frame(bad, "C2")


def test_validator_nan(synthetic_project):
    s = pd.read_parquet(schema.contract_path(synthetic_project, "C8", model="random"))
    s.loc[0, "score"] = float("nan")
    with pytest.raises(schema.ContractError, match="missing values"):
        schema.validate_frame(s, "C8")


def test_contract_path_needs_fields(synthetic_project):
    with pytest.raises(schema.ContractError):
        schema.contract_path(synthetic_project, "C2")


# ---------------------------------------------------------------- real project files


def test_real_project_files_match_contracts():
    """Validate whatever real contract files exist under data/ and outputs/ (skips if none)."""
    cfg = load_config()
    checked = schema.validate_project(cfg)
    if not checked:
        pytest.skip("no real contract files yet")
