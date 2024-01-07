function initMap() {
    const directionsService = new google.maps.DirectionsService();
    const directionsRenderer = new google.maps.DirectionsRenderer();

    const [latitudeMean, longitudeMean] = calculateCoordsMean(coordsList);
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 7,
        center: {lat: latitudeMean, lng: longitudeMean},
    });

    directionsRenderer.setMap(map);

    displayRoute(
        coordsList,
        directionsService,
        directionsRenderer,
    );
}

function calculateCoordsMean(coordsList) {
    let totalLatitude = 0;
    let totalLongitude = 0;

    // 各座標の緯度と経度を合計
    for (const coord of coordsList) {
        const [latitude, longitude] = coord.split(',').map(parseFloat);
        totalLatitude += latitude;
        totalLongitude += longitude;
    }

    // 平均を計算
    const latitudeMean = totalLatitude / coordsList.length;
    const longitudeMean = totalLongitude / coordsList.length;

    // 緯度と経度の平均をタプルで返す
    return [latitudeMean, longitudeMean];
}

/**
 * @param coords_list
 * @param directionsService directionsService
 * @param directionsRenderer directionsRenderer
 * @see https://developers.google.com/maps/documentation/javascript/reference/directions?hl=ja#DirectionsRequest
 */
function displayRoute(coords_list, directionsService, directionsRenderer) {
    directionsService
        .route({
            origin: coords_list.shift(),
            destination: coords_list.pop(),
            waypoints: coords_list.map(location => ({location})),
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
