class CustomMap {
    constructor(mapId, shopsInfo) {
        this.map = null;
        this.initialize(mapId, shopsInfo);
    }

    async initialize(mapId, shopsInfo) {
        const options = {
            zoom: 14,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: false,
            keyboardShortcuts: false,
            streetViewControl: false,
            fullscreenControl: false,
            scrollwheel: false
        };

        const data = JSON.parse(shopsInfo);
        this.map = new google.maps.Map(document.getElementById(mapId), options);
        this.map.setCenter(new google.maps.LatLng(data.center.lat, data.center.lng));
        this.createMarkers(data.shops);
    }

    createMarkers(shops) {
        shops.forEach(shop => {
            const latlng = new google.maps.LatLng(shop.geometry.location.lat, shop.geometry.location.lng);
            const marker = new google.maps.Marker({
                position: latlng,
                map: this.map,
                animation: google.maps.Animation.DROP,
                title: shop.shop_name // マウスオーバー時のツールチップとして店名を表示
            });

            marker.addListener('click', () => this.showShopDetails(marker, shop));
        });
    }

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
                const data = await response.json();
                let content = '';
                if (data.detail) { // data.detail が存在しない場合のエラーを回避
                    content += `名前: ${data.detail.name}<br>`;
                    content += `住所: ${data.detail.formatted_address.slice(0, 10)}...<br>`;
                    content += `電話番号: ${data.detail.formatted_phone_number}<br>`;
                    if (data.detail.opening_hours && data.detail.opening_hours.periods && data.detail.opening_hours.periods[0]) { // opening_hoursなどが存在しない場合のエラーを回避
                        content += `開店時間[Sun]: ${data.detail.opening_hours.periods[0].open.time}-${data.detail.opening_hours.periods[0].close.time}<br>`;
                    }
                    content += `料金レベル: ${data.detail.price_level}<br>`;
                    content += `評価: ${data.detail.rating}<br>`;
                    content += `種類: ${(data.detail.types || []).join(', ')}<br>`; // typesが存在しない場合のエラーを回避
                    content += `website: ${data.detail.website}<br><br>`;
                    if (data.detail.reviews && data.detail.reviews[0]) { // reviewsが存在しない場合のエラーを回避
                        content += `レビュー(先頭1名): <br>${data.detail.reviews[0].author_name}(${data.detail.reviews[0].rating}): ${data.detail.reviews[0].text}<br>`;
                    }
                } else {
                    content = "詳細情報を取得できませんでした。";
                }
                placeInformation.innerHTML = content;
                infoWindow.setContent(content); // 情報ウィンドウの内容を更新
            } catch (error) {
                console.error("Error:", error);
                placeInformation.innerHTML = "エラーが発生しました。";
                infoWindow.setContent("エラーが発生しました。");
            }
        }
    }
}

function do_pattern2(button) {
    console.log('is_editing: ', is_editing)
    if (!is_editing) {
        // red: 選択中
        button.style.border = 'solid 2px #ff0000';
        button.style.color = '#ff0000';
        alert('管理者選択モード');
    } else {
        // blue: 登録対象のピン
        const confirm = window.confirm("登録しますか？");
        if (confirm) {
            fetch(myUrl.base + 'search/2', {
                method: 'POST',
                headers: {
                    "Content-Type": "application/json; charset=utf-8",
                    "X-CSRFToken": Cookies.get('csrftoken')
                },
                body: JSON.stringify({"shops": keep_markers})
            })
                .then(response => response.json())
                .then(json => {
                    alert(json.status + ': 登録が完了しました。');
                    keep_markers = [];
                    location.href = myUrl.base + 'result/2';
                    button.style.border = 'solid 2px';
                    button.style.color = '#67c5ff';
                })
                .catch(error => {
                    shopinfomation.innerHTML = "Status: " + error.status + "\nError: " + error.message;
                })
        }
    }
    is_editing = !is_editing;
}
