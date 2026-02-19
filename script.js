function reminder(id) {
    fetch(`/reminder/${id}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById("msg").value = data.message;
            document.getElementById("modal").style.display = "block";
        });
}

function closeModal() {
    document.getElementById("modal").style.display = "none";
}

function copyMsg() {
    let txt = document.getElementById("msg");
    txt.select();
    document.execCommand("copy");
    alert("Copied!");
}
