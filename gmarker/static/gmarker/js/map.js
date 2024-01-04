let map;
const markers = [];
let infowindow;
let json;
let is_editing = false;
let keep_markers = [];

function mapinit(_json) {

    const options = {
        zoom: 14,
        mapTypeId: google.maps.MapTypeId.ROADMAP, // 既定: いつもの地図タイプ
        mapTypeControl: false, // 左上「地図／航空写真」切り替えボタン off
        keyboardShortcuts: false, // キーボードコントロール off
        streetViewControl: false, // ストリートビュー off
        fullscreenControl: false, // フルスクリーン off
        scrollwheel: false // マウスホイールスクロール off
    };
    // create canvas
    json = JSON.parse(_json);
    map = new google.maps.Map(document.getElementById("map_canvas1"), options);
    map.setCenter(new google.maps.LatLng(json["center"]["lat"], json["center"]["lng"]));
    createMarkers(json);
}

// get_category が使います
function createMarkers(json) {
    let latlng;
    if (typeof json != 'undefined' && json.shops.length > 0) {
        for (let i = 0; i < json.shops.length; i++) {
            latlng = new google.maps.LatLng(json.shops[i].geometry.location.lat, json.shops[i].geometry.location.lng);
            markers[i] = new google.maps.Marker({
                position: latlng,
                map: map,
                animation: google.maps.Animation.DROP
            });
            markerEvent(i);
        }
    }
}

// createMarkers が使います
function markerEvent(i) {
    markers[i].addListener('click', function () {
        if (!is_editing) {
            if (typeof infowindow != 'undefined') {
                infowindow.close();
            }
            infowindow = new google.maps.InfoWindow({
                content: json.shops[i]['shop_name']
            });
            infowindow.open(map, markers[i]);
            shopinfomation.innerHTML = '名前: ' + json.shops[i]['shop_name'];

            if (json.shops[i]['place_id'] != null) {
                // get a shop detail
                fetch(myurl.base + 'search/detail/' + json.shops[i]['place_id'], {
                    method: 'POST',
                    headers: {
                        "Content-Type": "application/json; charset=utf-8",
                        "X-CSRFToken": Cookies.get('csrftoken')
                    },
                    body: JSON.stringify({"shops": keep_markers})
                })
                    .then(response => response.json())
                    .then(json => {
                        let txt = '';
                        txt += '名前: ' + json.detail.name + '<br>';
                        txt += '住所: ' + json.detail.formatted_address.slice(0, 10) + '...<br>';
                        txt += '電話番号: ' + json.detail.formatted_phone_number + '<br>';
                        txt += '開店時間[Sun]: ' + json.detail.opening_hours.periods[0].open.time + '-';
                        txt += json.detail.opening_hours.periods[0].close.time + '<br>';
                        txt += '料金レベル: ' + json.detail.price_level + '<br>';
                        txt += '評価: ' + json.detail.rating + '<br>';
                        txt += '種類: ' + (json.detail.types).join(', ') + '<br>';
                        txt += 'website: ' + json.detail.website + '<br><br>';
                        txt += 'レビュー(先頭1名): <br>' + json.detail.reviews[0].author_name + '(' + json.detail.reviews[0].rating + ')' + ': ' + json.detail.reviews[0].text + '<br>'
                        shopinfomation.innerHTML = txt;
                    })
                    .catch(error => {
                        shopinfomation.innerHTML = "Status: " + error.status + "\nError: " + error.message;
                    })
            }
        } else {
            keep_markers.push(json.shops[i])
            markers[i].setMap(null);
            console.log('ok! this is it! keeeep!')
        }
    });
    markers[i].addListener('mouseover', function () {
        if (is_editing) {
            infowindow = new google.maps.InfoWindow({
                content: json.shops[i]['shop_name']
            });
            infowindow.open(map, markers[i]);
        }
        shopinfomation.innerHTML = '名前: ' + json.shops[i]['shop_name'];
    });
    markers[i].addListener('mouseout', function () {
        if (typeof infowindow != 'undefined') {
            infowindow.close();
        }
        shopinfomation.innerHTML = "";
    });
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
            fetch(myurl.base + 'search/2', {
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
                    location.href = myurl.base + 'result/2';
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
