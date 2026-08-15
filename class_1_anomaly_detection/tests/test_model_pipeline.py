from decimal import Decimal
import json
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from class_1_anomaly_detection.src.model_pipeline import (
    ModelGraph, build_anchor_diffs, build_bc_evidence, build_class1_pipeline,
    build_gadnr_features, build_model_graph, model_edge_index, role_percentiles,
    run_gadnr, serialize_class1_pipeline, serialize_service_results,
)


def fact(rows):
    frame = pd.DataFrame(rows, columns=empty_monthly_fact().columns)
    for column in (
        "month", "src_company_id", "dst_company_id", "product_id",
        "item_group_id", "item_name_id", "supplier_type", "receiver_type",
        "supplier_region", "receiver_region", "source_version", "quality_flags",
    ):
        frame[column] = frame[column].astype("string")
    for column in (
        "tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count", "unique_udi_count", "active_day_count",
    ):
        frame[column] = frame[column].astype("Int64")
    return frame


def row(month, src, dst, product="1", *, tx=1, amount=Decimal("1"), raw=Decimal("2"),
        piece=Decimal("3"), amount_valid=None, raw_valid=None, piece_valid=None,
        src_role="distributor", dst_role="hospital", src_region="r1", dst_region="r2"):
    product_id = "p3:" + product.zfill(64)
    return [
        month, src, dst, product_id, "g", "n", tx, amount,
        tx if amount_valid is None else amount_valid,
        raw, tx if raw_valid is None else raw_valid,
        piece, tx if piece_valid is None else piece_valid,
        tx, 1, src_role, dst_role, src_region, dst_region, "v", "",
    ]


class ModelPipelineTests(unittest.TestCase):

    def test_gadnr_backbone_only_consumes_tot_nodes(self):
        class FakeGCN:
            def __init__(self, *, in_channels, unexpected=None):
                if unexpected is not None:
                    raise TypeError("unexpected keyword argument 'unexpected'")
                self.in_channels = in_channels

        torch_geometric = types.ModuleType("torch_geometric")
        nn = types.ModuleType("torch_geometric.nn")
        models = types.ModuleType("torch_geometric.nn.models")
        models.GCN = FakeGCN
        torch_geometric.nn = nn
        nn.models = models
        with patch.dict(sys.modules, {
            "torch_geometric": torch_geometric,
            "torch_geometric.nn": nn,
            "torch_geometric.nn.models": models,
        }):
            from class_1_anomaly_detection.src.model_pipeline import run_gadnr

            # Extract the compatibility class through a minimal actual run
            # would require all optional ML modules.  Instead, duplicate the
            # public GAD-NR constructor call in a local fake detector.
            class FakeTensor:
                def reshape(self, *_):
                    return self

                def contiguous(self):
                    return self

            class FakeTorch:
                float32 = object()
                long = object()

                class cuda:
                    @staticmethod
                    def is_available():
                        return False

                @staticmethod
                def manual_seed(_):
                    return None

                @staticmethod
                def tensor(*_, **__):
                    return FakeTensor()

            captured = {}

            class FakeGADNR:
                def __init__(self, *, backbone, **_):
                    captured["backbone"] = backbone
                    captured["model"] = self

                def fit(self, _):
                    backbone = captured["backbone"]
                    self.encoder = backbone(in_channels=3, tot_nodes=2)
                    self.decision_score_ = [0.25, 0.75]

            data_module = types.ModuleType("torch_geometric.data")
            data_module.Data = lambda **kwargs: kwargs
            pygod = types.ModuleType("pygod")
            detector = types.ModuleType("pygod.detector")
            detector.GADNR = FakeGADNR
            pygod.detector = detector
            with patch.dict(sys.modules, {
                "torch": FakeTorch,
                "torch_geometric.data": data_module,
                "pygod": pygod,
                "pygod.detector": detector,
            }):
                graph = build_model_graph(fact([row("202401", "a", "b")]), anchor_month="202401")
                features, _ = build_gadnr_features(fact([row("202401", "a", "b")]), graph,
                                                   region_vocabulary=())
                self.assertEqual(run_gadnr(features, graph), [0.25, 0.75])
                self.assertEqual(captured["model"].encoder.in_channels, 3)
                with self.assertRaisesRegex(TypeError, "unexpected"):
                    captured["backbone"](in_channels=3, unexpected=True)

    def test_anchor_window_ends_at_anchor_across_year_boundary(self):
        graph = build_model_graph(fact([row("202311", "a", "b")]), anchor_month="202401")
        self.assertEqual(graph.window_months, ("202311", "202312", "202401"))

    def test_pair_collapse_distinct_product_self_loop_and_decimal_quality(self):
        rows = [
            row("202311", "a", "b", "1", tx=2, amount=Decimal("10"), raw=Decimal("4"), piece=Decimal("8")),
            row("202312", "a", "b", "2", tx=2, amount=None, raw=Decimal("5"), piece=None,
                amount_valid=0, raw_valid=1, piece_valid=0),
            row("202401", "a", "a", "3"),
        ]
        graph = build_model_graph(fact(rows), anchor_month="202401")
        edge = graph.edges.iloc[0]
        self.assertEqual((len(graph.edges), graph.self_loop_count, edge.unique_product_count), (1, 1, 2))
        self.assertEqual(edge.amount_sum_clean, Decimal("10"))
        self.assertEqual(edge.raw_supply_qty_valid_rate, Decimal("0.750000"))
        self.assertEqual(edge.piece_qty_valid_rate, Decimal("0.500000"))

    def test_all_null_quantity_preserves_null_sum_and_zero_coverage(self):
        graph = build_model_graph(fact([
            row("202401", "a", "b", raw=None, raw_valid=0, piece=None, piece_valid=0),
        ]), anchor_month="202401")
        edge = graph.edges.iloc[0]
        self.assertIsNone(edge.raw_supply_qty_sum)
        self.assertIsNone(edge.piece_qty_sum)
        self.assertEqual(edge.raw_supply_qty_valid_rate, Decimal("0.000000"))

    def test_edge_index_uses_graph_node_order_and_empty_shape(self):
        graph = build_model_graph(fact([row("202401", "z", "a")]), anchor_month="202401")
        self.assertEqual(graph.nodes, ("a", "z"))
        self.assertEqual(model_edge_index(graph), ((1,), (0,)))
        empty = ModelGraph("202401", ("202401",), ("isolated",), graph.edges.iloc[0:0], 0)
        self.assertEqual(model_edge_index(empty), ((), ()))
        scores = run_gadnr(pd.DataFrame(index=pd.Index(["isolated"], name="entity_id")), empty,
                           scorer=lambda x, edge: [0.0])
        self.assertEqual(scores, [0.0])

    def test_feature_roles_regions_valid_rates_and_exclusions(self):
        f = fact([
            row("202401", "a", "b", src_role="manufacturer", src_region="r1"),
            row("202312", "a", "c", "2", src_role="importer", src_region=None,
                raw=None, raw_valid=0, piece=None, piece_valid=0),
        ])
        graph = build_model_graph(f, anchor_month="202401")
        features, manifest = build_gadnr_features(f, graph, region_vocabulary=("r1", "r2"))
        self.assertEqual(manifest["entity_metadata"]["a"]["role_group"], "multi_role")
        self.assertTrue(manifest["entity_metadata"]["a"]["region_missing_or_conflict"])
        self.assertIn("out_raw_supply_qty_valid_rate", features)
        self.assertIn("out_piece_qty_valid_rate", features)
        self.assertTrue(set(("bc", "edge_attr", "unique_udi_count")).issubset(manifest["excluded_features"]))

    def test_decimal_log_is_clipped_deterministically_without_overflow(self):
        f = fact([row("202401", "a", "b", amount=Decimal("1e9999"), raw=Decimal("1e9999"))])
        graph = build_model_graph(f, anchor_month="202401")
        first, manifest = build_gadnr_features(f, graph, region_vocabulary=())
        second, _ = build_gadnr_features(f, graph, region_vocabulary=())
        pd.testing.assert_frame_equal(first, second)
        self.assertTrue(np_isfinite(first.to_numpy(dtype=float)).all())
        self.assertEqual(manifest["log_transform"]["clip_max"], "1E+100")

    def test_run_rejects_external_node_order_and_lazy_dependency_error(self):
        f = fact([row("202401", "a", "b")])
        graph = build_model_graph(f, anchor_month="202401")
        features, _ = build_gadnr_features(f, graph, region_vocabulary=())
        with self.assertRaisesRegex(ValueError, "ordering"):
            run_gadnr(features.iloc[::-1], graph, scorer=lambda x, edge: [0, 0])
        with patch.dict("sys.modules", {"pygod": None, "torch": None}):
            with self.assertRaisesRegex(RuntimeError, "optional"):
                run_gadnr(features, graph)

    def test_role_percentile_ties_minimum_and_anchor_partition(self):
        scores = pd.DataFrame({
            "anchor_month": ["202401"] * 3 + ["202402"],
            "role_group": ["hospital"] * 4,
            "raw_score": [1.0, 1.0, 3.0, 99.0],
        })
        ranked = role_percentiles(scores, minimum_sample=3)
        self.assertEqual(list(ranked.loc[:1, "review_priority_percentile"]), [50.0, 50.0])
        self.assertEqual(ranked.loc[2, "review_priority_percentile"], 100.0)
        self.assertTrue(ranked.loc[3, "insufficient_sample"])
        self.assertEqual(ranked.loc[3, "reason"], "role_group_below_minimum_sample")

    def test_both_diff_definitions_use_correct_windows_and_decimal(self):
        f = fact([
            row("202308", "a", "old", amount=Decimal("2")),
            row("202310", "a", "lost", "2", amount=Decimal("3")),
            row("202311", "a", "kept", "3", amount=Decimal("5")),
            row("202401", "a", "new", "4", amount=Decimal("11")),
        ])
        previous, nonoverlap = build_anchor_diffs(f, anchor_month="202401", entities=("a",))
        self.assertEqual(previous["a"]["new_counterparty_ids"], ("new",))
        self.assertEqual(previous["a"]["lost_counterparty_ids"], ("lost",))
        self.assertEqual(previous["a"]["retained_counterparty_ids"], ("kept",))
        self.assertEqual(nonoverlap["a"]["comparison_months"], ("202308", "202309", "202310"))
        self.assertEqual(nonoverlap["a"]["amount_change"], Decimal("11"))

    def test_bc_gateway_fractional_path_and_zero_reachable_evidence(self):
        f = fact([
            row("202401", "s", "g1", "1", src_role="manufacturer", dst_role="distributor"),
            row("202401", "s", "g2", "2", src_role="manufacturer", dst_role="distributor"),
            row("202401", "g1", "t", "3", src_role="distributor", dst_role="hospital"),
            row("202401", "g2", "t", "4", src_role="distributor", dst_role="hospital"),
        ])
        graph = build_model_graph(f, anchor_month="202401")
        _, manifest = build_gadnr_features(f, graph, region_vocabulary=())
        evidence = build_bc_evidence(graph, manifest["entity_metadata"], minimum_role_sample=1)
        self.assertEqual(evidence["g1"]["gateway_share"], Decimal("0.5"))
        self.assertEqual(evidence["g1"]["weak_component_size"], 4)
        self.assertFalse(evidence["g1"]["insufficient_evidence"])
        self.assertEqual(evidence["g1"]["bc_rank"], 1.5)
        self.assertEqual(evidence["g1"]["bc_percentile"], 75.0)
        none = build_bc_evidence(graph, {node: {"role_group": "unknown"} for node in graph.nodes})
        self.assertTrue(none["g1"]["insufficient_evidence"])
        self.assertEqual(none["g1"]["reason"], "no_reachable_source_target_pairs")

    def test_bc_modes_are_deterministic_and_defer_before_large_pair_materialization(self):
        f = fact([
            row("202401", "s1", "g", "1", src_role="manufacturer", dst_role="distributor"),
            row("202401", "s2", "g", "2", src_role="importer", dst_role="distributor"),
            row("202401", "g", "t1", "3", src_role="distributor", dst_role="hospital"),
            row("202401", "g", "t2", "4", src_role="distributor", dst_role="hospital"),
        ])
        graph = build_model_graph(f, anchor_month="202401")
        _, manifest = build_gadnr_features(f, graph, region_vocabulary=())
        sampled_a = build_bc_evidence(graph, manifest["entity_metadata"], exact_pair_limit=1,
                                      maximum_pair_limit=10, sample_pairs=2, seed=3)
        sampled_b = build_bc_evidence(graph, manifest["entity_metadata"], exact_pair_limit=1,
                                      maximum_pair_limit=10, sample_pairs=2, seed=3)
        self.assertEqual(sampled_a, sampled_b)
        self.assertEqual(sampled_a["g"]["mode"], "deterministic_sample")
        deferred = build_bc_evidence(graph, manifest["entity_metadata"], maximum_pair_limit=1)
        self.assertEqual(deferred["g"]["mode"], "deferred_too_large")
        self.assertEqual(deferred["g"]["reason"], "graph_too_large")

    def test_bc_dependency_handles_exponentially_many_diamond_paths_without_enumerating(self):
        levels = 24
        nodes = ["source"] + [f"n{level}_{side}" for level in range(levels) for side in range(2)] + ["target"]
        edges = []
        for side in range(2):
            edges.append({"src_company_id": "source", "dst_company_id": f"n0_{side}"})
        for level in range(levels - 1):
            for left in range(2):
                for right in range(2):
                    edges.append({"src_company_id": f"n{level}_{left}", "dst_company_id": f"n{level + 1}_{right}"})
        for side in range(2):
            edges.append({"src_company_id": f"n{levels - 1}_{side}", "dst_company_id": "target"})
        graph = ModelGraph("202401", ("202401",), tuple(nodes), pd.DataFrame(edges), 0)
        metadata = {node: {"role_group": "distributor"} for node in nodes}
        metadata["source"] = {"role_group": "manufacturer"}
        metadata["target"] = {"role_group": "hospital"}
        evidence = build_bc_evidence(graph, metadata, minimum_role_sample=2)
        self.assertEqual(evidence["n12_0"]["gateway_share"], Decimal("0.5"))
        self.assertEqual(evidence["n12_0"]["mode"], "exact")

    def test_bc_role_rankings_are_separate_from_gadnr_features_and_raw_stays_qa_only(self):
        f = fact([
            row("202401", "s", "g1", "1", src_role="manufacturer", dst_role="distributor"),
            row("202401", "s", "g2", "2", src_role="manufacturer", dst_role="distributor"),
            row("202401", "g1", "t", "3", src_role="distributor", dst_role="hospital"),
            row("202401", "g2", "t", "4", src_role="distributor", dst_role="hospital"),
        ])
        graph = build_model_graph(f, anchor_month="202401")
        features, manifest = build_gadnr_features(f, graph, region_vocabulary=())
        evidence = build_bc_evidence(graph, manifest["entity_metadata"], minimum_role_sample=2)
        self.assertEqual(evidence["g1"]["bc_role_group_sample_size"], 2)
        self.assertEqual(evidence["g1"]["bc_rank"], 1.5)
        self.assertEqual(evidence["g1"]["bc_percentile"], 75.0)
        self.assertNotIn("bc_rank", features.columns)
        self.assertNotIn("bc_percentile", features.columns)
        result = build_class1_pipeline(f, anchor_month="202401", model_version="m1",
                                       scorer=lambda x, edge: [0.0] * len(x),
                                       minimum_role_sample=2, region_vocabulary=())
        self.assertIn("bc_raw", result.bc_evidence["g1"])
        self.assertNotIn("bc_raw", result.service_results.iloc[0].bc_evidence)

    def test_pipeline_manifest_service_serializer_are_deterministic_and_hide_raw(self):
        f = fact([row("202401", "a", "b", src_role="manufacturer")])
        scorer = lambda features, edge: [float(index) for index in range(len(features))]
        first = build_class1_pipeline(f, anchor_month="202401", model_version="m1",
                                      scorer=scorer, seed=7, minimum_role_sample=1,
                                      region_vocabulary=("r1", "r2"))
        second = build_class1_pipeline(f.iloc[::-1], anchor_month="202401", model_version="m1",
                                       scorer=scorer, seed=7, minimum_role_sample=1,
                                       region_vocabulary=("r1", "r2"))
        payload = serialize_class1_pipeline(first)
        self.assertEqual(payload, serialize_class1_pipeline(second))
        self.assertNotIn("raw_score", json.dumps(payload))
        self.assertEqual(first.manifest["seed"], 7)
        self.assertEqual(first.manifest["graph_summary"]["edge_count"], 1)

    def test_service_serializer_allowlist(self):
        output = serialize_service_results(pd.DataFrame({
            "entity_id": ["a"], "anchor_month": ["202401"],
            "raw_score": [9.0], "company_name": ["secret"],
        }))
        self.assertEqual(output, [{"entity_id": "a", "anchor_month": "202401"}])


def np_isfinite(values):
    import numpy as np
    return np.isfinite(values)
