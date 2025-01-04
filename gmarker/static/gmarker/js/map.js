let markers = [];
let infoWindow;

class MarkerData {
    constructor(data) {
        this.lat = data.location.lat;
        this.lng = data.location.lng;
        this.title = data.name || "マーカー";
        this.placeId = data.place_id;
        this.rating = data.rating;
    }

    toHtml() {
        return `
          <div>
            <p>${this.title}</p>
            <p>Place ID: ${this.placeId}<br>lat,lng: ${this.lat},${this.lng}<br>rating: ${this.rating}</p>
          </div>
        `;
    }
}

function initMap(jsonData) {
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
            showInfoWindow(marker, markerData.toHtml());
        });

        return {marker, data: markerData};
    });
}

function showInfoWindow(marker, content) {
    if (infoWindow) {
        infoWindow.close();
    }
    infoWindow = new google.maps.InfoWindow({content});
    infoWindow.open(map, marker);
}
