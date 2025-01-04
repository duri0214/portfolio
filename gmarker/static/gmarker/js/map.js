let markers = [];
let infowindow;

class MarkerData {
    constructor(data) {
        this.lat = data.location.lat;
        this.lng = data.location.lng;
        this.title = data.name || "マーカー";
        this.placeId = data.place_id;
    }
}

function initMap(jsonData) {
    console.log("initMap called", jsonData);
    try {
        if (!jsonData) {
            console.error("jsonData is not defined.");
            return;
        }

        const {Map, Marker} = google.maps;

        const options = {
            zoom: 14,
            center: new google.maps.LatLng(jsonData.center.lat, jsonData.center.lng),
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: false,
            keyboardShortcuts: false,
            streetViewControl: false,
            fullscreenControl: false,
            scrollwheel: true
        };

        map = new Map(document.getElementById("map_canvas1"), options);
        console.log(jsonData.places);
        createMarkersFromData(jsonData.places, Marker, map);

    } catch (e) {
        console.error("Google Maps API の初期化エラー:", e);
        alert("地図の読み込みに失敗しました。インターネット接続を確認してください。");
    }
}

function createMarkersFromData(places, Marker, map) {
    if (!map || !places || !Marker) {
        console.error("Missing map, places, or Marker");
        return;
    }

    markers = places.map(place => {
        const markerData = new MarkerData(place);
        const marker = new Marker({
            position: new google.maps.LatLng(markerData.lat, markerData.lng),
            map: map,
            animation: google.maps.Animation.DROP,
            title: markerData.title
        });

        marker.addListener('click', () => {
            showInfoWindow(marker, markerData.title);
            showShopInformation(markerData);
        });

        return {marker, data: markerData};
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

async function showShopInformation(markerData) {
    const placeInformation = document.getElementById('placeInformation');
    if (!placeInformation) return;
    placeInformation.innerHTML = '名前: ' + markerData.title;
    if (markerData.placeId) {
        try {
            const response = await fetch(myUrl.base + 'search/detail/' + markerData.placeId);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const json = await response.json();
            placeInformation.innerHTML += '<br>詳細情報: ' + JSON.stringify(json);
        } catch (error) {
            console.error("詳細情報の取得エラー:", error);
            placeInformation.innerHTML += '<br>詳細情報の取得に失敗しました。';
        }
    }
}
