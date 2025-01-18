from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.valueobject.order import OrderPair


class OrderBookService:
    @staticmethod
    def calculate_order_book():
        # 集計済みの売り注文と買い注文を取得
        sell_orders = OrderRepository.get_sell_orders_grouped()
        buy_orders = OrderRepository.get_buy_orders_grouped()

        # 結果を格納するリスト
        result_list = []

        # 売り注文と買い注文のポインタ
        sell_pointer = 0
        buy_pointer = 0

        # 売り注文と買い注文を順番に処理
        while sell_pointer < len(sell_orders) and buy_pointer < len(buy_orders):
            sell_order = sell_orders[sell_pointer]
            buy_order = buy_orders[buy_pointer]

            sell_price = sell_order["price"]
            buy_price = buy_order["price"]

            if sell_price == buy_price:
                # 売りと買いの価格が一致する場合
                sell_quantity: int = sell_order["total_quantity"]
                buy_quantity: int = buy_order["total_quantity"]

                if sell_quantity > buy_quantity:  # 売りが多い場合
                    result_list.append(
                        OrderPair(
                            price=sell_price,
                            sell_quantity=sell_quantity - buy_quantity,
                            buy_quantity=0,
                        )
                    )
                elif buy_quantity > sell_quantity:  # 買いが多い場合
                    result_list.append(
                        OrderPair(
                            price=buy_price,
                            sell_quantity=0,
                            buy_quantity=buy_quantity - sell_quantity,
                        )
                    )
                else:  # 完全に一致する場合
                    result_list.append(
                        OrderPair(
                            price=sell_price,
                            sell_quantity=0,
                            buy_quantity=0,
                        )
                    )
                sell_pointer += 1
                buy_pointer += 1

            elif sell_price < buy_price:  # 売り価格が買い価格より低い場合
                result_list.append(
                    OrderPair(
                        price=sell_price,
                        sell_quantity=sell_order["total_quantity"],
                        buy_quantity=0,
                    )
                )
                sell_pointer += 1
            else:  # 売り価格が買い価格より高い場合
                result_list.append(
                    OrderPair(
                        price=buy_price,
                        sell_quantity=0,
                        buy_quantity=buy_order["total_quantity"],
                    )
                )
                buy_pointer += 1

        # 残りの売り注文を結果に追加
        for i in range(sell_pointer, len(sell_orders)):
            sell_order = sell_orders[i]
            result_list.append(
                OrderPair(
                    price=sell_order["price"],
                    sell_quantity=sell_order["total_quantity"],
                    buy_quantity=0,
                )
            )
        # 残りの買い注文を結果に追加
        for i in range(buy_pointer, len(buy_orders)):
            buy_order = buy_orders[i]
            result_list.append(
                OrderPair(
                    price=buy_order["price"],
                    sell_quantity=0,
                    buy_quantity=buy_order["total_quantity"],
                )
            )

        # 価格順にソートして結果を返す
        result_list.sort(key=lambda x: x.price)  # リスト内の価格順を昇順にソート
        return result_list
