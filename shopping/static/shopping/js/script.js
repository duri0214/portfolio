let tr_edit;
let tr_prev;

function addRowHandler() {
    const table = edit_table.tBodies[0];
    const rows = table.rows;
    for (let i = 0; i < rows.length; i++) {
        if (table.rows[i].className == "") {
            table.rows[i].addEventListener('click', e => {
                const tr = e.target.parentNode;
                if (tr_edit != undefined && tr_prev == tr) {
                    tr_edit.style.display = "none";
                    tr_edit = undefined;
                } else {
                    if (tr_edit != undefined) {
                        tr_edit.style.display = "none";
                    }
                    tr_edit = tr.nextElementSibling;
                    tr_edit.style.display = "table-row";
                    tr_prev = tr;
                    fetch(myurl.base + "product/edit/0/", {
                        method: 'POST',
                        headers: {
                            "Content-Type": "application/json; charset=utf-8",
                            "X-CSRFToken": Cookies.get('csrftoken')
                        },
                        body: JSON.stringify({"code": tr.cells[0].textContent})
                    })
                        .then(response => response.json())
                        .then(json => {
                            const td_edit = tr_edit.cells[0];
                            td_edit.children[0].value = json.code;
                            td_edit.children[1].value = json.name;
                            td_edit.children[2].value = json.price;
                            td_edit.children[3].value = json.description;
                        })
                }
            }, false)
        }
    }
}
