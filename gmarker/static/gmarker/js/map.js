/**
 * 店舗詳細情報のVO（Value Object）。
 */
class ShopDetail {
    /**
     * @param {Object} data APIから取得した店舗詳細データ。
     */
    constructor(data) {
        this.name = data.name || "情報なし";
        this.address = (data.formatted_address || "").slice(0, 10) + "...";
        this.phoneNumber = data.formatted_phone_number || "情報なし";
        this.openingHours = this.formatOpeningHours(data.opening_hours);
        this.priceLevel = data.price_level || "情報なし";
        this.rating = data.rating || "情報なし";
        this.types = (data.types || []).join(', ') || "情報なし";
        this.website = data.website || "情報なし";
        this.review = this.formatReview(data.reviews);
    }

    /**
     * 開店時間をフォーマットする。
     * @param {Object} openingHours 開店時間データ。
     * @returns {string} フォーマットされた開店時間文字列。
     */
    formatOpeningHours(openingHours) {
        if (openingHours && openingHours.periods && openingHours.periods[0]) {
            return `${openingHours.periods[0].open.time}-${openingHours.periods[0].close.time}`;
        }
        return "情報なし";
    }

    /**
     * レビューをフォーマットする。
     * @param {Array<Object>} reviews レビューデータ配列。
     * @returns {string} フォーマットされたレビュー文字列。
     */
    formatReview(reviews) {
        if (reviews && reviews[0]) {
            return `${reviews[0].author_name}(${reviews[0].rating}): ${reviews[0].text}`;
        }
        return "情報なし";
    }


    /**
     * HTML文字列を生成する。
     * @returns {string} HTML文字列。
     */
    toHtml() {
        return `
            名前: ${this.name}<br>
            住所: ${this.address}<br>
            電話番号: ${this.phoneNumber}<br>
            開店時間[Sun]: ${this.openingHours}<br>
            料金レベル: ${this.priceLevel}<br>
            評価: ${this.rating}<br>
            種類: ${this.types}<br>
            website: ${this.website}<br><br>
            レビュー(先頭1名):<br> ${this.review}<br>
        `;
    }
}

/**
 * Google Maps上にマーカーを表示し、クリックで詳細情報を表示するクラス。
 */
class CustomMap {
    /**
     * CustomMapのコンストラクタ。
     * @param {string} mapId マップを表示するdiv要素のID。
     * @param {string} shopsInfo 店舗情報を含むJSON文字列。
     */
    constructor(mapId, shopsInfo) {
        /**
         * Google Mapsのインスタンス。
         * @type {google.maps.Map}
         */
        this.map = null;
        this.initialize(mapId, shopsInfo);
    }

    /**
     * マップの初期化を行う。
     * @async
     * @param {string} mapId マップを表示するdiv要素のID。
     * @param {string} shopsInfo 店舗情報を含むJSON文字列。
     */
    async initialize(mapId, shopsInfo) {
        /**
         * Google Mapsのオプション。
         * @type {google.maps.MapOptions}
         */
        const options = {
            zoom: 14,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: false,
            keyboardShortcuts: false,
            streetViewControl: false,
            fullscreenControl: false,
            scrollwheel: false
        };

        try {
            /**
             * 店舗データ。
             * @type {Object}
             */
            const data = JSON.parse(shopsInfo);
            this.map = new google.maps.Map(document.getElementById(mapId), options);
            this.map.setCenter(new google.maps.LatLng(data.center.lat, data.center.lng));
            this.createMarkers(data.shops);
        } catch (error) {
            console.error("JSON parse error:", error);
            // JSONパースエラー時の処理を追加（例：エラーメッセージ表示）
        }

    }

    /**
     * マーカーを生成し、マップに配置する。
     * @param {Array<Object>} shops 店舗情報の配列。
     */
    createMarkers(shops) {
        shops.forEach(shop => {
            const latlng = new google.maps.LatLng(shop.geometry.location.lat, shop.geometry.location.lng);
            /**
             * Google Mapsのマーカー。
             * @type {google.maps.Marker}
             */
            const marker = new google.maps.Marker({
                position: latlng,
                map: this.map,
                animation: google.maps.Animation.DROP,
                title: shop.shop_name // マウスオーバー時のツールチップ
            });

            // TODO: クリックするとどんどんレイヤー張って上に重なるからシングルトンにして
            marker.addListener('click', () => this.showShopDetails(marker, shop));
        });
    }

    /**
     * マーカークリック時に店舗詳細情報を表示する。
     * @async
     * @param {google.maps.Marker} marker クリックされたマーカー。
     * @param {Object} shop 店舗情報。
     */
    async showShopDetails(marker, shop) {
        let infoWindow = new google.maps.InfoWindow();
        infoWindow.setContent(shop.shop_name);
        infoWindow.open(this.map, marker);

        if (shop.place_id) {
            try {
                const response = await fetch(myUrl.base + 'search/detail/' + shop.place_id, {
                    method: 'POST',
                    headers: {
                        "Content-Type": "application/json; charset=utf-8",
                        "X-CSRFToken": Cookies.get('csrftoken')
                    }
                });
                if (!response.ok) {
                    const errorJson = await response.json();
                    throw new Error(`${response.status} ${response.statusText}: ${errorJson.message}`);
                }
                const data = await response.json();

                // VOを作成
                const shopDetail = new ShopDetail(data.detail || {});
                console.log("shopDetail: ", shopDetail)

                placeInformation.innerHTML = shopDetail.toHtml();
                infoWindow.setContent(shopDetail.toHtml());
            } catch (error) {
                console.error("Error:", error);
                placeInformation.innerHTML = "エラーが発生しました。";
                infoWindow.setContent("エラーが発生しました。");
            }
        }
    }
}

/**
 * ピンを選択して登録するモードの処理を行う関数。
 * @param {HTMLButtonElement} button クリックされたボタン要素。
 */
async function toggleEditMode(button) {
    /**
     * 現在編集モードかどうかを示すフラグ。static変数として定義することで、関数呼び出しを超えて状態を保持
     * @type {boolean}
     */
    toggleEditMode.isEditing = toggleEditMode.isEditing === undefined ? false : !toggleEditMode.isEditing;

    if (!toggleEditMode.isEditing) {
        // 選択モード開始時のスタイル変更
        button.style.border = 'solid 2px #ff0000';
        button.style.color = '#ff0000';
        alert('管理者選択モード');
    } else {
        // 登録確認ダイアログを表示
        const confirmed = window.confirm("登録しますか？");
        if (confirmed) {
            try {
                // 登録処理を実行
                const response = await fetch(myUrl.base + 'search/2', {
                    method: 'POST',
                    headers: {
                        "Content-Type": "application/json; charset=utf-8",
                        "X-CSRFToken": Cookies.get('csrftoken')
                    },
                    body: JSON.stringify({"shops": keep_markers})
                });

                if (!response.ok) {
                    // HTTPエラーの場合、エラーをthrow
                    const errorJson = await response.json(); //サーバーからエラーメッセージが返ってきている場合
                    throw new Error(`${response.status} ${response.statusText}: ${errorJson.message}`);
                }
                const json = await response.json();

                alert(json.status + ': 登録が完了しました。');
                keep_markers = [];
                location.href = myUrl.base + 'result/2';

                // 登録完了後のスタイル変更
                button.style.border = 'solid 2px';
                button.style.color = '#67c5ff';

            } catch (error) {
                console.error("登録エラー:", error);
                shopinfomation.innerHTML = `Status: ${error.message}`; // エラーメッセージを表示
            }
        } else {
            // キャンセルされた場合は編集モードを戻す
            toggleEditMode.isEditing = !toggleEditMode.isEditing;
            button.style.border = 'solid 2px'; // 元のスタイルに戻す
            button.style.color = '#67c5ff';
        }
    }
}
