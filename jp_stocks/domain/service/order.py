from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.valueobject.order import OrderSummary, OrderPair


class OrderBookService:
    @staticmethod
    def calculate_order_book():
        # 集計済みの売り・買い注文を取得
        sell_orders = OrderRepository.get_sell_orders_grouped()
        buy_orders = OrderRepository.get_buy_orders_grouped()

        # 結果を格納するリスト
        result_pairs = []

        # 売りと買いのポインタ
        sell_pointer = 0
        buy_pointer = 0

        # 売り注文と買い注文を順番に処理
        while sell_pointer < len(sell_orders) and buy_pointer < len(buy_orders):
            sell_order = OrderSummary(
                price=sell_orders[sell_pointer]["price"],
                total_quantity=sell_orders[sell_pointer]["total_quantity"],
            )
            buy_order = OrderSummary(
                price=buy_orders[buy_pointer]["price"],
                total_quantity=buy_orders[buy_pointer]["total_quantity"],
            )

            # 1. 完全一致 (=)
            if sell_order.price == buy_order.price:
                sell_net_quantity, buy_net_quantity = (
                    OrderBookService._process_exact_match(
                        sell_order.total_quantity, buy_order.total_quantity
                    )
                )
                result_pairs.append(
                    OrderPair(
                        sell_order=OrderSummary(
                            price=sell_order.price, total_quantity=sell_net_quantity
                        ),
                        buy_order=OrderSummary(
                            price=buy_order.price, total_quantity=buy_net_quantity
                        ),
                    )
                )

                # 小さくなったほうを 0 と比較してポインタを進める
                if sell_net_quantity == 0:
                    sell_pointer += 1
                if buy_net_quantity == 0:
                    buy_pointer += 1

            # 2. 売り価格 < 買い価格
            elif sell_order.price < buy_order.price:
                # この売り注文に残る数量すべてを OrderPair に追加
                result_pairs.append(
                    OrderPair(
                        sell_order=OrderSummary(
                            price=sell_order.price,
                            total_quantity=sell_order.total_quantity,
                        ),
                        buy_order=None,
                    )
                )

                # 売り注文だけ処理が終わったのでポインタを進める
                sell_pointer += 1

            # 3. 売り価格 > 買い価格
            else:
                result_pairs.append(
                    OrderPair(
                        sell_order=None,
                        buy_order=OrderSummary(
                            price=buy_order.price,
                            total_quantity=buy_order.total_quantity,
                        ),
                    )
                )

                buy_pointer += 1

        # 売り注文と買い注文の残りを結果に追加
        for i in range(sell_pointer, len(sell_orders)):
            result_pairs.append(
                OrderPair(
                    sell_order=OrderSummary(
                        price=sell_orders[i]["price"],
                        total_quantity=sell_orders[i]["total_quantity"],
                    ),
                    buy_order=None,
                )
            )
        for i in range(buy_pointer, len(buy_orders)):
            result_pairs.append(
                OrderPair(
                    sell_order=None,
                    buy_order=OrderSummary(
                        price=buy_orders[i]["price"],
                        total_quantity=buy_orders[i]["total_quantity"],
                    ),
                )
            )

        return result_pairs

    @staticmethod
    def _process_exact_match(sell_quantity, buy_quantity):
        """
        売り数量と買い数量を比較し、相殺後の残りの数量（ネット数量）を返却する。
        sell_quantity: 売り注文の総量
        buy_quantity: 買い注文の総量
        戻り値: (売りのネット数量, 買いのネット数量)
        """
        if sell_quantity > buy_quantity:
            return sell_quantity - buy_quantity, 0
        elif buy_quantity > sell_quantity:
            return 0, buy_quantity - sell_quantity
        else:
            return 0, 0  # 完全相殺


class OrderMatchingService:
    """
    注文のマッチングを管理するサービスクラス。
    """

    @staticmethod
    def match_and_save_order(new_order):
        """
        新しい注文をマッチングし、保存する。
        対象の反対方向の注文を処理する。
        """
        # 反対方向の注文を取得
        opposite_orders = OrderRepository.get_opposite_orders(
            side=new_order.side,
            price=new_order.price,
        )

        # ロジック確認用: 対象となる注文をログ出力
        print(
            f"[SERVICE] Found {len(opposite_orders)} orders to match with: {new_order}."
        )

        # シンプルなマッチング処理 (詳細なマッチングロジックはここに実装)
        for order in opposite_orders:
            # TODO: 実際の数量計算や取引ロジックをここに記述
            print(
                f"[MATCHED] New order {new_order} matches with existing order {order}."
            )

        # 新しい注文を保存
        OrderRepository.save_order(new_order)
