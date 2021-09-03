function likes(event, user_id, article_id) {
    console.log(user_id)
    if(user_id !== "None"){
        fetch(myurl.base + 'likes/' + user_id + '/' + article_id + '/', {
                method: 'POST',
                headers: {
                    "Content-Type": "application/json; charset=utf-8",
                    "X-CSRFToken": Cookies.get('csrftoken')
                },
            body: JSON.stringify({"status": "requested by javascript."})
            }
        )
        .then(response => response.json())
        .then(json => {
            // json-value
            console.log(json)
            // state of 'like'
            const is_pressed = (event.target.getAttribute("aria-pressed") === "true");
            event.target.setAttribute("aria-pressed", !is_pressed);
            // count of 'like' ±1
            const tag_span = event.target.getElementsByTagName('span')[0];
            let coefficient = !is_pressed ? +1 : -1
            let cnt = tag_span.innerHTML.match(/\((.+)\)/)[1]; // e.g. (3) => 3
            tag_span.innerHTML = tag_span.innerHTML.replace(cnt, parseInt(cnt) + coefficient);
        })
    } else {
        location.href=myurl.login;
    }
}
