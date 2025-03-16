function initMap() {
    const directionsService = new google.maps.DirectionsService();
    const directionsRenderer = new google.maps.DirectionsRenderer();

    const [latitudeMean, longitudeMean] = calculateCoordListMean(coordList);
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 7,
        center: {lat: latitudeMean, lng: longitudeMean},
    });

    directionsRenderer.setMap(map);

    displayRoute(
        coordList,
        directionsService,
        directionsRenderer,
    );
}

function calculateCoordListMean(coordList) {
    let totalLatitude = 0;
    let totalLongitude = 0;

    // 各座標の緯度と経度を合計
    for (const coord of coordList) {
        const [latitude, longitude] = coord.split(',').map(parseFloat);
        totalLatitude += latitude;
        totalLongitude += longitude;
    }

    // 平均を計算
    const latitudeMean = totalLatitude / coordList.length;
    const longitudeMean = totalLongitude / coordList.length;

    // 緯度と経度の平均をタプルで返す
    return [latitudeMean, longitudeMean];
}

/**
 * @param coord_list
 * @param directionsService directionsService
 * @param directionsRenderer directionsRenderer
 * @see https://developers.google.com/maps/documentation/javascript/reference/directions?hl=ja#DirectionsRequest
 */
function displayRoute(coord_list, directionsService, directionsRenderer) {
    directionsService
        .route({
            origin: coord_list.shift(),
            destination: coord_list.pop(),
            waypoints: coord_list.map(location => ({location})),
            travelMode: google.maps.TravelMode.DRIVING,
            avoidTolls: true,  // 有料道路を除外
            optimizeWaypoints: true  // 地点最適化
        })
        .then((result) => {
            directionsRenderer.setDirections(result);
        })
        .catch((e) => {
            alert("Could not display directions due to: " + e);
        });
}

window.initMap = initMap;
