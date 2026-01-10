"""
このファイルは試作品（プロトタイプ）です。
lib.llm に並ぶ他のライブラリとは品質や設計の意図が異なります。

【研究背景・ステータス】
本プロトタイプは「男と女の認知差や比喩表現のニュアンスを日常語彙（Twitter等）で見る」ことを目的としています。
既存のニュースコーパス等と比較して、Twitterの生の発言データは人間の感覚差やニュアンスのズレを抽出するのに最適であるという
アプローチに基づいて設計されました。

しかし、Twitter API (v2 Free tier) の極めて厳しいレート制限（429 Too Many Requests）により、
継続的なデータ収集と分析の運用には制約があります。
現在は「日常語彙の意味空間解析装置」としての設計プロトタイプを完走させた状態でマージ・クローズされており、
実運用においてはレート制限のリセットを待つ等の対応が必要な「御蔵入り（参照用資材）」扱いのステータスです。
"""

import os
import re
import time
import logging
from datetime import datetime
import numpy as np
import pandas as pd
import tweepy
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from lib.llm.prototype.semantic_kawaii_and_taste_vo import (
    TweetText,
    TweetCollection,
    EmbeddingVector,
    EmbeddingCollection,
    SimilarityResult,
    SimilarityMatrix,
)

load_dotenv()

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticKawaiiAndTasteService:

    def __init__(self):
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer_token:
            logger.warning("TWITTER_BEARER_TOKEN is not set.")

        self.twitter_client = tweepy.Client(bearer_token=bearer_token)
        # 文埋め込みモデルのロード
        self.embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    # ---------------------------
    # Tweet収集
    # ---------------------------
    def fetch_tweets(self, query: str, category: str) -> TweetCollection:
        tweets = []
        try:
            # Free tier 制限対策: max_results は 10 固定
            max_results = 10
            resp = self.twitter_client.search_recent_tweets(
                query=query,
                tweet_fields=["text", "lang"],
                max_results=max_results,
            )

            if resp.data:
                for t in resp.data:
                    if t.lang == "ja":
                        cleaned = self._clean_text(t.text)
                        tweets.append(TweetText(text=cleaned))
        except tweepy.TooManyRequests as tmr_error:
            reset_time_str = "Unknown"
            remaining_seconds = "Unknown"

            # Response header からリセット時刻を取得
            if hasattr(tmr_error, "response") and tmr_error.response is not None:
                reset_timestamp = tmr_error.response.headers.get("x-rate-limit-reset")
                if reset_timestamp:
                    try:
                        reset_ts = int(reset_timestamp)
                        reset_time = datetime.fromtimestamp(reset_ts)
                        reset_time_str = reset_time.strftime("%Y-%m-%d %H:%M:%S")
                        remaining_seconds = max(0, int(reset_ts - time.time()))
                    except (ValueError, TypeError):
                        pass

            logger.error(
                f"Rate limit exceeded for {category}. "
                f"Reset at: {reset_time_str} ({remaining_seconds}s remaining). Aborting."
            )
            raise
        except Exception as exc:
            logger.error(f"Error fetching tweets for {category}: {exc}")
            raise

        return TweetCollection(category=category, tweets=tweets)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"http\S+", "", text)
        text = re.sub(r"@\w+", "", text)
        return text.strip()

    # ---------------------------
    # Embedding生成
    # ---------------------------
    def build_embeddings(self, collection: TweetCollection) -> EmbeddingCollection:
        if not collection.tweets:
            return EmbeddingCollection(category=collection.category, embeddings=[])

        texts = [t.text for t in collection.tweets]
        vectors = self.embedding_model.encode(texts)

        embeddings = [
            EmbeddingVector(text=text, vector=vec) for text, vec in zip(texts, vectors)
        ]

        return EmbeddingCollection(category=collection.category, embeddings=embeddings)

    # ---------------------------
    # 類似度計算
    # ---------------------------
    @staticmethod
    def calc_similarity(
        a: EmbeddingCollection, b: EmbeddingCollection
    ) -> SimilarityMatrix:

        if not a.embeddings or not b.embeddings:
            # 片方が空の場合のダミー
            stats = SimilarityResult(mean=0.0, median=0.0, max=0.0, min=0.0)
            return SimilarityMatrix(
                category_a=a.category,
                category_b=b.category,
                matrix=np.array([[]]),
                stats=stats,
            )

        a_vecs = np.array([emb.vector for emb in a.embeddings])
        b_vecs = np.array([emb.vector for emb in b.embeddings])

        sim_matrix = cosine_similarity(a_vecs, b_vecs)

        stats = SimilarityResult(
            mean=float(sim_matrix.mean()),
            median=float(np.median(sim_matrix)),
            max=float(sim_matrix.max()),
            min=float(sim_matrix.min()),
        )

        return SimilarityMatrix(
            category_a=a.category, category_b=b.category, matrix=sim_matrix, stats=stats
        )

    # ---------------------------
    # CSV出力
    # ---------------------------
    @staticmethod
    def export_similarity_csv(sim: SimilarityMatrix, path: str):
        # ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        df = pd.DataFrame(sim.matrix.flatten(), columns=["similarity"])
        df.to_csv(path, index=False)

    # ---------------------------
    # 実行パイプライン
    # ---------------------------
    def run_pipeline(self):
        kawaii_query = "かわいい -is:retweet lang:ja"
        taste_query = (
            "(味がする OR 甘い OR 旨い OR 酸っぱい OR しょっぱい) -is:retweet lang:ja"
        )

        logger.info(f"Fetching tweets for query: {kawaii_query}")
        kawaii = self.fetch_tweets(kawaii_query, "kawaii")

        # レート制限対策のスリープ
        logger.info("Waiting for 5 seconds to avoid rate limit...")
        time.sleep(5)

        logger.info(f"Fetching tweets for query: {taste_query}")
        taste = self.fetch_tweets(taste_query, "taste")

        if not kawaii.tweets or not taste.tweets:
            logger.error(
                "No tweets found for one or more categories. Aborting pipeline."
            )
            return None

        logger.info("Building embeddings...")
        kawaii_emb = self.build_embeddings(kawaii)
        taste_emb = self.build_embeddings(taste)

        logger.info("Calculating similarity...")
        similarity = self.calc_similarity(kawaii_emb, taste_emb)

        output_path = "data/semantic_kawaii_and_taste_similarity.csv"
        logger.info(f"Exporting results to {output_path}...")
        self.export_similarity_csv(similarity, output_path)

        return similarity


if __name__ == "__main__":
    service = SemanticKawaiiAndTasteService()
    try:
        result = service.run_pipeline()

        if result:
            print("\nSemantic Similarity Stats")
            print(f"Mean:   {result.stats.mean:.4f}")
            print(f"Median: {result.stats.median:.4f}")
            print(f"Max:    {result.stats.max:.4f}")
            print(f"Min:    {result.stats.min:.4f}")
        else:
            print("\nPipeline failed to produce results.")
    except Exception as pipeline_error:
        print(f"\nPipeline aborted due to error: {pipeline_error}")
