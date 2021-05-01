JSON_HEADERS = ["Content-Type", "application/json"];

/*
 *  @param type (string)    : request type ['GET', 'POST', 'PUT', etc.]
 *  @param url (string)     : url to send request to
 *  @param onload (function): request response callback function (passed request object as param)
 *  @param header (array)*  : array of key/value pairs for setting heaeder elements
 *  @param payload (json)*  : data to send alongside the request
 *
 *  Note: params with an '*' are optional
 */
function sendRequest(type, url, onload, header=[], payload=null){
    var xh = new XMLHttpRequest();
    xh.onload = () => {onload(xh);};
    xh.open(type, url);
    header.forEach(elem => xh.setRequestHeader(elem[0], elem[1]));
    if(payload != null)
        xh.send(payload);
    else
        xh.send();
}

function sendJson(url, onload, payload, type='POST', header=[]){
    sendRequest(type, url, onload, header.concat([JSON_HEADERS]), payload);
}

function redirect(url){
    window.location.replace(url);
}

function error(msg){
    $('#errorAlert').text(msg).show();
}

function info(msg){
    $('#infoAlert').text(msg).show();
}

function modal(msg, onconfirm){
    $('#modalConfirm').modal('show');
    $('#modalBody').text(msg);
    $('#modalYes').click((e) => {
        onconfirm(e);
    });
}

function searchSong(query){
    var roomNum = $('#roomNum').val();
    if (roomNum == '0'){
        error('Please select a room number first!');
        return;
    }
    return redirect('/?query=' + query + '&room=' + $('#roomNum').val());
}

function requestSong(uri){
    var payload = document.getElementById(uri).value.replaceAll("'", '"');
    sendJson(
        '/request/' + $('#roomNum').val(),
        (xh)=>{
            var jr = JSON.parse(xh.response);
            if(jr.result)
                info(jr.message);
            else
                error(jr.message);
        },
        payload
    );
}

function approveSong(uri){
    redirect('/auth/index?func=approve_song&song=' + uri);
}

function denySong(uri){
    redirect('/auth/index?func=deny_song&song=' + uri);
}

function blockSong(uri){
    modal('Are you sure you want to add this song to your blocklist?',
        (e) => { redirect('/auth/index?func=block_song&song=' + uri) }
    );
}

function unblockSong(uri){
    modal('Are you sure you want to remove this song to your blocklist?',
        (e) => { redirect('/auth/index?func=unblock_song&song=' + uri) }
    );
}

$(document).ready(function() {
    feather.replace();
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    $('#query').val(urlParams.get('query'));
    $('#search').click((e)=>{
        searchSong($('#query').val());
    });
    $('#roomSelect').change((e)=>{
        $('#roomNum').val($(this).find('option:selected').text());
    });
    $('.alert').hide();
    $('.alert').click((e)=>{
        $('#' + e.target.id).hide();
    });
    $('#err').show();
});
