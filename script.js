function updateLines(){
    let code = document.getElementById("code").value;
    let lines = code.split("\n").length;

    let nums = "";
    for(let i=1;i<=lines;i++){
        nums += i + "<br>";
    }

    document.getElementById("lines").innerHTML = nums;
}

// INITIAL
updateLines();

async function run(){

    let code = document.getElementById("code").value;
    let lang = document.getElementById("lang").value;

    let res = await fetch("http://127.0.0.1:5000/compile", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({code, lang})
    });

    let data = await res.json();

    if(data.error){
        document.getElementById("output").innerHTML =
            "<span style='color:red'>" + data.error + "</span>";
        return;
    }

    document.getElementById("output").innerHTML =
        "<span style='color:lightgreen'>Success</span>";

    document.getElementById("tokens").innerText = data.tokens.join(" ");
    document.getElementById("tree").innerText = data.tree;
    document.getElementById("semantic").innerText = data.semantic;
    document.getElementById("icg").innerText = data.icg;
    document.getElementById("opt").innerText = data.opt;
    document.getElementById("final").innerText = data.final;
}