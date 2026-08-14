from decimal import Decimal
import unittest
import pandas as pd
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from class_1_anomaly_detection.src.model_pipeline import build_model_graph, build_gadnr_features, run_gadnr, role_percentiles, serialize_service_results

def fact(rows):
    frame = pd.DataFrame(rows, columns=empty_monthly_fact().columns)
    for column in ("month","src_company_id","dst_company_id","product_id","item_group_id","item_name_id","supplier_type","receiver_type","supplier_region","receiver_region","source_version","quality_flags"):
        frame[column] = frame[column].astype("string")
    for column in ("tx_count","amount_valid_row_count","raw_supply_qty_valid_row_count","piece_qty_valid_row_count","unique_udi_count","active_day_count"):
        frame[column] = frame[column].astype("Int64")
    return frame

def row(month, src, dst, product, amount=Decimal("1"), raw=Decimal("2"), piece=Decimal("3")):
    return [month,src,dst,product,"g","n",1,amount,1,raw,1,piece,1,1,1,"distributor","hospital","r1","r2","v",""]

class ModelPipelineTests(unittest.TestCase):
    def test_pair_edges_collapse_products_and_preserve_decimal_attributes(self):
        f=fact([row("202401","a","b","p3:"+"1"*64),row("202402","a","b","p3:"+"2"*64),row("202403","a","a","p3:"+"3"*64)])
        graph=build_model_graph(f,anchor_month="202401")
        self.assertEqual(len(graph.edges),1); self.assertEqual(graph.self_loop_count,1)
        self.assertEqual(graph.edges.iloc[0].unique_product_count,2); self.assertIsInstance(graph.edges.iloc[0].amount_sum_clean,Decimal)
    def test_features_exclude_bc_and_edge_attributes_and_scorer_is_injected(self):
        f=fact([row("202401","a","b","p3:"+"1"*64)])
        graph=build_model_graph(f,anchor_month="202401"); features,manifest=build_gadnr_features(f,graph,region_vocabulary=("r1","r2"))
        self.assertNotIn("bc",features.columns); self.assertIn("edge_attr",manifest["excluded_features"])
        self.assertEqual(run_gadnr(features,[(0,1)],scorer=lambda x,e:[7.0]*len(x)),[7.0,7.0])
    def test_percentile_and_service_serializer_hide_raw_score(self):
        scores=role_percentiles(pd.DataFrame({"role_group":["unknown"]*2,"raw_score":[1.0,2.0]}),minimum_sample=3)
        self.assertTrue(scores.insufficient_sample.all())
        result=serialize_service_results(pd.DataFrame({"entity_id":["a"],"raw_score":[9.0],"company_name":["no"],"anchor_month":["202401"]}))
        self.assertEqual(result,[{"entity_id":"a","anchor_month":"202401"}])
