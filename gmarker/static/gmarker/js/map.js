/**
 * マーカーに紐付けるデータのインターフェース
 * @class MarkerData
 */
class MarkerData {
    /**
     * MarkerDataオブジェクトを生成する
     * @constructor
     * @param {Object} data - マーカーの元データ
     * @param {Object} data.geometry - ジオメトリ情報
     * @param {Object} data.geometry.location - 位置情報
     * @param {string|number} data.geometry.location.lat - 緯度
     * @param {string|number} data.geometry.location.lng - 経度
     * @param {string} [data.shop_name] - 店舗名 (オプション)
     * @param {string} [data.place_id] - Place ID (オプション)
     * @param {number} [data.radius] - 半径 (オプション)
     * @param {string} [data.name] - 名称 (shop_nameがない場合に使用)
     */
    constructor(data) {
        this.lat = data.geometry.location.lat;
        this.lng = data.geometry.location.lng;
        this.title = data.shop_name || data.name || "マーカー";
        this.placeId = data.place_id;
        this.radius = data.radius;
    }
}

class CustomMap {
    constructor(mapCanvasId, jsonData) {
        this.map = new google.maps.Map(document.getElementById(mapCanvasId), {
            zoom: 14,
            center: new google.maps.LatLng(jsonData.center.lat, jsonData.center.lng)
        });
        this.addMarkers(jsonData.shops);
    }

    addMarkers(shops) {
        shops.forEach(shop => {
            new google.maps.Marker({
                position: new google.maps.LatLng(shop.geometry.location.lat, shop.geometry.location.lng),
                map: this.map,
                title: shop.shop_name
            });
        });
    }
}

let map;
let markers = [];
let infowindow;
let jsonData;
let isEditing = false;
let selectedMarkers = [];

function initMap(jsonString) {
    jsonData = JSON.parse(jsonString);

    const options = {
        zoom: 14,
        center: new google.maps.LatLng(jsonData.center.lat, jsonData.center.lng),
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        mapTypeControl: false,
        keyboardShortcuts: false,
        streetViewControl: false,
        fullscreenControl: false,
        scrollwheel: true // マウスホイールスクロールは有効に
    };

    map = new google.maps.Map(document.getElementById("map_canvas1"), options);

    createMarkersFromData(jsonData.shops);

    // ローカルストレージからisEditingの状態を復元
    const storedIsEditing = localStorage.getItem('isEditing');
    if (storedIsEditing) {
        isEditing = JSON.parse(storedIsEditing);
    }

    // 編集モードに応じてイベントリスナーを設定
    updateMarkerListeners();
}

function createMarkersFromData(shops) {
    markers = shops.map(shop => {
        const markerData = new MarkerData(shop);
        const marker = new google.maps.Marker({
            position: new google.maps.LatLng(markerData.lat, markerData.lng),
            map: map,
            animation: google.maps.Animation.DROP
        });
        return {marker, data: markerData}; // マーカーオブジェクトとデータオブジェクトを保持
    });
}


function updateMarkerListeners() {
    markers.forEach((markerObj, i) => {
        const {marker, data} = markerObj;
        google.maps.event.clearListeners(marker, 'click'); // 既存のリスナーをクリア
        google.maps.event.clearListeners(marker, 'mouseover');
        google.maps.event.clearListeners(marker, 'mouseout');

        if (isEditing) {
            marker.addListener('click', () => {
                if (selectedMarkers.includes(data)) {
                    // 選択済みなら選択解除
                    selectedMarkers = selectedMarkers.filter(m => m !== data);
                    marker.setIcon(null); // アイコンを元に戻すなどの処理
                } else {
                    // 未選択なら選択
                    selectedMarkers.push(data);
                    marker.setIcon({ // アイコンを変更して選択状態を表現
                        url: "https://maps.google.com/mapfiles/ms/icons/green-dot.png" // 例: 緑のアイコン
                    });
                }
                console.log('選択されたマーカー:', JSON.stringify(selectedMarkers));
            });
            marker.addListener('mouseover', () => {
                showInfoWindow(marker, data.shopName);
            });
            marker.addListener('mouseout', () => {
                closeInfoWindow();
            });
        } else {
            marker.addListener('click', () => {
                showInfoWindow(marker, data.shopName);
                showShopInformation(data);
            });
        }
    });
}

function showInfoWindow(marker, content) {
    if (infowindow) {
        infowindow.close();
    }
    infowindow = new google.maps.InfoWindow({content});
    infowindow.open(map, marker);
}

function closeInfoWindow() {
    if (infowindow) {
        infowindow.close();
        infowindow = null;
    }
}

function showShopInformation(markerData) {
    placeInformation.innerHTML = '名前: ' + markerData.shopName;
    if (markerData.placeId) {
        fetch(myUrl.base + 'search/detail/' + markerData.placeId, { /* ... */})
            .then(response => response.json())
            .then(json => { /* ... */
            })
            .catch(error => { /* ... */
            });
    }
}

function toggleEditMode(button) {
    isEditing = !isEditing;
    localStorage.setItem('isEditing', JSON.stringify(isEditing)); // 状態を保存
    updateMarkerListeners(); // リスナーを更新

    if (isEditing) {
        button.style.border = 'solid 2px #ff0000';
        button.style.color = '#ff0000';
        alert('管理者選択モード');
    } else {
        button.style.border = 'solid 2px';
        button.style.color = '#67c5ff';
        const confirm = window.confirm("登録しますか？");
        if (confirm && selectedMarkers.length > 0) {
            fetch(myUrl.base + 'search/2', {
                method: 'POST',
                headers: {
                    "Content-Type": "application/json; charset=utf-8",
                    "X-CSRFToken": Cookies.get('csrftoken')
                },
                body: JSON.stringify({places: selectedMarkers.map(markerData => markerData.shop)}) // shopオブジェクト全体を送信
            })
                .then(response => response.json())
                .then(json => {
                    alert(json.status + ': 登録が完了しました。');
                    location.href = myUrl.base + 'search/2';
                    button.style.border = 'solid 2px';
                    button.style.color = '#67c5ff';
                })
                .catch(error => {
                    placeInfomation.innerHTML = "Status: " + error.status + "\nError: " + error.message;
                });
        }
        selectedMarkers = []; // 選択をクリア
    }
}