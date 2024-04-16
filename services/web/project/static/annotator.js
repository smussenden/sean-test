function enableAnnotationMode(){
    //myDragon.setMouseNavEnabled(false);
    myDragon.gestureSettingsMouse.clickToZoom = false;

    // Make the highlight and highlightactivated boxes clickable:
    myDragon.interaction_mode = 'annotation';
}

function disableAnnotationMode(){
    //myDragon.setMouseNavEnabled(true);
    // NOTE if mobile support, might need to also do other nav types:
    myDragon.gestureSettingsMouse.clickToZoom = true;
    
    // Disable click to change status of overlay box:
    myDragon.interaction_mode = 'navigation';
}

// TODO should probaly combine w/ annotationmode functions:
function enableSplitMode(type){
    //myDragon.setMouseNavEnabled(false);
    myDragon.gestureSettingsMouse.clickToZoom = false;

    // Make the highlight and highlightactivated boxes clickable:
    if (type == 'vertical') { 
        myDragon.interaction_mode = 'vert_split';
    }
    else if (type == 'horizontal') { 
        myDragon.interaction_mode = 'hor_split';
    }
}

function setActiveArticle(artnum) {
    if (artnum > 0) {
        artnum -= 1;
    }
    else {
        artnum = 9;
    }

    // Update UI -- highlight the corresponding article box.
    // First, un-highlight current active article:
    var art = articleManager.articles[activeArticle];
    art.toggleSidebarHighlight(false);
    
    activeArticle = artnum;
    var art = articleManager.articles[activeArticle];
    art.toggleSidebarHighlight(true);
}

function disableSplitMode(){
    // NOTE if mobile support, might need to also do other nav types:
    myDragon.gestureSettingsMouse.clickToZoom = true;
    
    // Disable click to change status of overlay box:
    myDragon.interaction_mode = 'navigation';
}

function addHighlight(el_clicked) {
    el_clicked.className = el_clicked.className.replace( /(?:^|\s)highlight(?!\S)/g , 'highlightactivated' );

    // Update description in myDragon.overlays:
    console.log(el_clicked.id);
    var the_overlay = myDragon.overlays.filter( obj => { return obj.id === el_clicked.id } )[0]
    the_overlay.className = 'highlightactivated';
    
    // Update article membership:
    console.log('the overlay id clicked: ' + the_overlay.id);
    articleManager.addOverlayToArticle(the_overlay.id, activeArticle);
}

function highlightClickHandler(e) {
    if (myDragon.interaction_mode == 'annotation') {
        pushState(); // Update history
        redo_stack = [];

        var el_clicked = e.originalTarget;
        // Do nothing if element clicked has ID starting with 'KL_'
        if (el_clicked.id.startsWith('KL_')) {
            return;
        }

        // remove highlight
        if (el_clicked.className.match(/(?:^|\s)highlightactivated(?!\S)/)) {
            
            var current_article_id = articleManager.articleFromOverlayID(el_clicked.id).id;

            // remove Highlight if the current article is same as the active article
            if (current_article_id == activeArticle) {
                el_clicked.className = el_clicked.className.replace( /(?:^|\s)highlightactivated(?!\S)/g , 'highlight' );

                // Update description in myDragon.overlays:
                var the_overlay = myDragon.overlays.filter( obj => { return obj.id === el_clicked.id } )[0]
                the_overlay.className = 'highlight';
                
                // Update article membership:
                articleManager.removeHighlight(the_overlay.id);
            }
            // Otherwise just reassign the overlay to different article.
            else {
                addHighlight(el_clicked);
            }
            
        // add highlight
        } else {
            addHighlight(el_clicked);
        }

        // enable saving
        document.getElementById("save_new_button").disabled = false;
        if (page_details.mod_id != 0) {
            document.getElementById("save_button").disabled = false;
        }
        else { // necessary when saving is enabled by modifying flags/notes
            document.getElementById("save_button").disabled = true;
        }
    }
    else if (myDragon.interaction_mode == 'hor_split') {
    //else if (myDragon.interaction_mode == 'hor_split' || myDragon.interaction_mode == 'vert_split') {
        pushState();
        redo_stack = []; // TODO should encapsulate all interactions with state into an object which abstracts away undo/redo stack management.

        splitOverlay(e);
    }
}

function splitOverlay(clickevent) {
    var click_pt = myDragon.viewport.pointFromPixel(clickevent.position);

    var o_id = clickevent.originalTarget.id;
    var o_bounds = myDragon.getOverlayById(o_id).bounds;

    // New bounds for the two overlays:
    var ob = o_bounds;
    var b1 = new OpenSeadragon.Rect(ob.x, ob.y, ob.width, ob.height, ob.degrees);
    var b2 = new OpenSeadragon.Rect(ob.x, ob.y, ob.width, ob.height, ob.degrees);
    // TODO if clicked within 10 pixels of the box's border, do nothing.

    if (myDragon.interaction_mode == 'hor_split') {
        b1.height = click_pt.y - b1.y; // Upper rectangle

        // Lower rectangle:
        b2.y = click_pt.y;
        b2.height = o_bounds.height - b1.height;
    }
    else {
        b1.width= click_pt.x - b1.x; // Left rectangle

        // Right rectangle:
        b2.x = click_pt.x;
        b2.width= o_bounds.width - b1.width;
    }

    console.log('original:', o_bounds);
    console.log('b1:', b1);
    console.log('b2:', b2);

    // Remove the overlay that was clicked.
    var orig_article = articleManager.articleFromOverlayID(o_id);
    if (orig_article != -1) { 
        console.log(orig_article.id);
        articleManager.removeHighlight(o_id);
    }

    myDragon.removeOverlay(o_id);

    // Add the new overlays.
    // Create elements for them.
    // Naming convention:  append "_1" and "_2" to id.
    var elt1 = document.createElement("div");
    elt1.id = o_id + '_1';
    console.log(clickevent);
    elt1.className = clickevent.originalTarget.className;
    myDragon.addOverlay({
        element: elt1,
        location: b1 
    });
    var elt2 = document.createElement("div");
    elt2.id = o_id + '_2';
    elt2.className = clickevent.originalTarget.className;
    myDragon.addOverlay({
        element: elt2,
        location: b2 
    });

    // Update myDragon.overlays:
    myDragon.overlays = myDragon.overlays.filter( obj => { return obj.id !== o_id } );
    myDragon.overlays.push({
        className: elt1.className,
        height: b1.height,
        id: elt1.id,
        width: b1.width,
        x: b1.x,
        y: b1.y,
    });
    myDragon.overlays.push({
        className: elt2.className,
        height: b2.height,
        id: elt2.id,
        width: b2.width,
        x: b2.x,
        y: b2.y,
    });

    // Assign overlays to same article as their predecessor.
    if (orig_article.id != -1) {
        console.log('arttt' + orig_article.id);
        articleManager.addOverlayToArticle(elt1.id, orig_article.id);
        articleManager.addOverlayToArticle(elt2.id, orig_article.id);
    }


    // NOTE splitting boxes should enable saving...?
}
 
function getHighlightedBoxes() {
    // TODO unused -- remove?
    var boxes = [];
    var overlays_by_id = {};
    myDragon.overlays.forEach(function (o) {
        overlays_by_id[o.id] = o;
    });
    console.log(overlays_by_id);

    // All elements of class highlightactivated.
    $('.highlightactivated').each(function(index) {
        var overlay_id = $(this)[0].id;
        console.log(overlay_id);
        boxes.push(overlays_by_id[overlay_id]);
    });
    // Get their dimensions.
    return boxes
}

function savePage(is_new_annotation) {
    // Emit a message to the 'send_message' socket
    var box_data = myDragon.overlays;
    box_data.forEach( function (o) {
        var art = articleManager.articleFromOverlayID(o.id);
        if (art == -1) {
            o.article_id = -1;
        } else {
            o.article_id = articleManager.articleFromOverlayID(o.id).id;
        }
        o.KEYWORD_STATS = keyline_stats[o.id];
    });
    console.log(box_data);

    page_details['notes'] = $('#notes')[0].value;
    var flag_string = '';

    page_details['flag_irrelevant'] = $('#flag_irrelevant')[0].checked;
    page_details['flag_other'] = $('#flag_other')[0].checked;
    page_details['flag_bad_layout'] = $('#flag_bad_layout')[0].checked;

    console.log(page_details)

    // Get the user id from the url args:
    var url = new URL(window.location.href);
    var user_id = url.searchParams.get("user_id");

    // is_new_annotation tells server whether to save or overwrite
    socket.emit('save_page', {'page_details' : page_details, 'box_data' : box_data, 'is_new_annotation' : is_new_annotation, 'user_id' : user_id });

    //// If page was flagged as unuseful, then always save that status to the original page as well.
    //if ((page_details['flag_irrelevant'] || page_details['flag_bad_layout']) &&
    //    is_new_annotation)
    //{
    //    socket.emit('save_page', {'page_details' : page_details, 'box_data' : box_data, 'is_new_annotation' : false });
    //}

    document.getElementById("save_new_button").disabled = true;
    document.getElementById("save_button").disabled = true;
}

var socket;
function setupSocketIO() {
    // The http vs. https is important. Use http for localhost!
    // So, we check if we're on localhost, and if so, use http.
    // Otherwise, use https.
    var url = new URL(window.location.href);
    var connection_domain_prefix = 'https://';
    if (url.hostname == 'localhost' || url.hostname == '127.0.0.1') {
        connection_domain_prefix = 'http://';
        console.log("Dev mode. Using http with socketio");
    }
    socket = io.connect(connection_domain_prefix + document.domain + ':' + location.port);

    socket.emit('page_opened', {'file_id' : page_details.file_id});

    // Handler for save_failed - call saveFailedHandler
    socket.on('save_failed', function(msg) {
        console.log('save_failed');
        console.log(msg);
        saveFailedHandler(msg);
    });

    // Button was clicked
    document.getElementById("save_button").onclick = function() { savePage(false); }
    document.getElementById("save_new_button").onclick = function() { savePage(true); }
}

function saveFailedHandler(msg) {
    // Display an alert with the message.
    alert(msg['message']);
}

function setupDragonJS() {
    // Try to disable fancy interpolation
    var canvases = document.getElementsByTagName("canvas");
    for(var i = 0; i < canvases.length; i++){
        canvases[i].style.imageRendering = "-moz-crisp-edges";
        canvases[i].getContext.mozImageSmoothingEnabled = false;
    }

    // Enable interaction with OpenSeadragon
    var content = document.getElementsByClassName('passive');
    for (var i = 0 ; i < content.length ; i++) {
        content[i].className = content[i].className.replace(' passive', '');
    }    

    // onclick for highlight boxes, for annotation mode:
    myDragon.addHandler('canvas-click', highlightClickHandler);

    // Toggling between annotation and navigation modes:
    document.body.addEventListener('keydown', function (e) {
        if (e.key == 'e' && myDragon.interaction_mode !== 'annotation') {
            enableAnnotationMode();
        }
        else if (e.key == 'v' && myDragon.interaction_mode !== 'vert_split') {
            enableSplitMode('vertical');
        }
        else if (e.key == 't' && myDragon.interaction_mode !== 'hor_split') {
            enableSplitMode('horizontal');
        }
        else if (['1','2','3','4','5','6','7','8','9','0'].includes(e.key)) {
            setActiveArticle(parseInt(e.key));
        }
        else if (e.key == 'ArrowRight' || e.key == 'D') {
            goToNextKeyView();
        }
        else if (e.key == 'ArrowLeft' || e.key == 'A') {
            goToPrevKeyView();
        }//, "ArrowLeft", "ArrowUp", or "ArrowDown
    });
    
    document.body.addEventListener('keyup', function (e) {
        if (e.key == 'e' && myDragon.interaction_mode == 'annotation') {
            disableAnnotationMode()
        }
        else if (e.key == 'v' && myDragon.interaction_mode == 'vert_split') {
            disableSplitMode('vertical');
        }
        else if (e.key == 't' && myDragon.interaction_mode == 'hor_split') {
            disableSplitMode('horizontal');
        }
    });

    // ctrl+s to save:
    $(window).bind('keydown', function(event) {
        if (event.ctrlKey || event.metaKey) {
            switch (String.fromCharCode(event.which).toLowerCase()) {
                case 's':
                    event.preventDefault();
                    save_new = event.shiftKey;
                    // Check button state to determine whether saving is currently allowed:
                    if ( (save_new && !(document.getElementById("save_new_button").disabled)) ||
                        (!save_new && !(document.getElementById("save_button").disabled)) ) {
                        savePage(save_new);

                        if (save_new) {
                            alert('Saved new annotation for this page.');
                        }
                        else {
                            alert('Saved changes to this annotation.');
                        }
                    }

                    break;
                case 'z':
                    event.preventDefault();
                    if (event.shiftKey ) {
                        redo();
                    }
                    else {
                        undo();
                    }
                    break;
            }
        }
    });
    
    // DISABLE keyboard shortcuts when typing in text boxes:
    $('#notes').on('keydown', function(e) {
        e.stopPropagation();
        console.log('notes keydown');
    });
    $('#notes').on('keyup', function(e) {

        e.stopPropagation();
        console.log('notes keyup');
    });
    $('#notes').on('keypress', function(e) {
        e.stopPropagation();
        console.log('notes keypress');
    });



    // Add an id for the overlay-containing div:
    $('.openseadragon-canvas > div')[0].id = 'overlay-container';

    // initialize history stack
    edit_history = []; 
    redo_stack = [];

    document.getElementById("undo_button").onclick = function() { undo(); }
    document.getElementById("redo_button").onclick = function() { redo(); }

    // Special behavior for flags which the user can save on without highlighting any
    // overlays:
    document.getElementById("flag_irrelevant").onclick = firstClassCheckboxClicked(this.id);
    document.getElementById("flag_bad_layout").onclick = firstClassCheckboxClicked(this.id);
}

function goToPrevKeyView() {
    var new_view = viewNavigator.prevView();
    var view_rect = new_view['view_rect'];
    myDragon.viewport.fitBounds(view_rect, true);
    console.log('Snapping to keyview ', new_view);
}

function goToNextKeyView() {
    var new_view = viewNavigator.nextView();
    var view_rect = new_view['view_rect'];
    myDragon.viewport.fitBounds(view_rect, true);
    console.log('Snapping to keyview ', new_view);

    //// Show the nav map for two seconds:
    //myDragon.navigator.element.style.display = "inline-block";
    //myDragon.addOnceHandler('hide-nav', function (e) {
    //    myDragon.navigator.element.style.display = "none";
    //});

    //setTimeout(function (e) {
    //    myDragon.raiseEvent('hide-nav');
    //}, 2000);


}

function firstClassCheckboxClicked() {
    // Enable SAVE, regardless of highlighting status.
    document.getElementById("save_button").disabled = false;
}

function pushState(onto_redo_stack = false) {
    var new_state = {
        'save_new_disabled' : document.getElementById("save_new_button").disabled,
        'save_disabled' : document.getElementById("save_button").disabled,
        'overlays' : [],
        'articles_by_overlay_id' : structuredClone(articleManager.getState())
    };

    myDragon.currentOverlays.forEach( function (o) {
        new_state['overlays'].push( {
            'id' : o.element.id,
            'className' : o.element.className,
            'bounds' : o.bounds
        });
    });

    if (onto_redo_stack) {
        redo_stack.push(new_state);
        document.getElementById("redo_button").disabled = false;
    }
    else {
        edit_history.push(new_state);
        console.log(edit_history);

        // Enable undo
        document.getElementById("undo_button").disabled = false;
    }
}

function redo() {
    // state is:  myDragon.overlays and the overlay-container div.
    if (redo_stack.length == 0) {
        return;
    }

    var redo_state = redo_stack.pop();
    console.log(redo_stack);

    // clear the overlays
    pushState(onto_redo_stack = false);
    myDragon.clearOverlays();
    // add new html
    //$('#overlay-container')[0].innerHTML = prev_state.overlay_html;
    // update prev_state.current_overlays so that elements point to currently existing elements.
    // for each overlay here^^^, call addOverlay.
    redo_state.overlays.forEach( function(o) {
        var elt = document.createElement("div");
        elt.id = o.id;
        elt.className = o.className;
        if (elt.className == 'highlightactivated') {
            console.log(o);
        }
        myDragon.addOverlay({
            element: elt,
            location: o.bounds
        });
    });

    // Now add the articles:
    delete articleManager;
    console.log(redo_state.articles_by_overlay_id);
    articleManager = new ArticleManager(articles_by_overlay_id = redo_state.articles_by_overlay_id);

    document.getElementById("save_new_button").disabled = redo_state.save_new_disabled;
    document.getElementById("save_button").disabled = redo_state.save_disabled;

    if (redo_stack.length == 0) {
        //document.getElementById("save_new_button").disabled = true;
        //document.getElementById("save_button").disabled = true;
        document.getElementById("redo_button").disabled = true;
    }
}

function undo() {
    // pop state from history stack.
    // state is:  myDragon.overlays and the overlay-container div.
    if (edit_history.length == 0) {
        return;
    }

    var prev_state = edit_history.pop();
    console.log(edit_history);
    //myDragon.overlays = prev_state.overlays;
    //myDragon.current_overlays = prev_state.current_overlays;
    //$('#overlay-container')[0].innerHTML = prev_state.overlay_html;

    // save state to redo stack, and clear the overlays
    pushState(onto_redo_stack = true);
    myDragon.clearOverlays();
    
    // for each overlay here^^^, call addOverlay.
    prev_state.overlays.forEach( function(o) {
        var elt = document.createElement("div");
        elt.id = o.id;
        elt.className = o.className;
        console.log(o.id);
        myDragon.addOverlay({
            element: elt,
            location: o.bounds
        });
    });

    // Now add the articles:
    delete ArticleManager;
    articleManager = new ArticleManager(articles_by_overlay_id = prev_state.articles_by_overlay_id);

    document.getElementById("save_new_button").disabled = prev_state.save_new_disabled;
    document.getElementById("save_button").disabled = prev_state.save_disabled;

    if (edit_history.length == 0) {
        document.getElementById("undo_button").disabled = true;
    }
}

var readyCount = 0;
function dragonReady() {
    if (++readyCount == 2) {
        console.log('dragonReady called 2 times. OpenSeadragon should have updated the DOM by now');
        console.log('SETTING UP DRAGON');
        setupDragonJS();

        // again for good measure... if socket exists
        if (socket) {
            socket.emit('page_opened', {'file_id' : page_details.file_id});
        }

        // Set up the article manager.
        // For some reason, overlays are cleared and re-added (sometimes repeatedly), so we need to add listeners to update the article manager as this happens.
        articleManager = new ArticleManager(articles_by_overlay_id = articles_by_overlay_id);

    }
}

// Event handlers etc. for stuff that doesn't use myDragon or socketio...
// Run after setupSocketIO() and setupDragonJS()
function setupEverythingElse() {
    // Modifying notes and flags enables saving:
    $(':checkbox').each(function() {
        this.addEventListener('input', function() {
            // dont enable saving for the original page, if boxes were highlighted.
            if (! (page_details['mod_id'] == 0 & edit_history.length > 0)) {
                document.getElementById("save_button").disabled = false;
            }
        })
    }, false);

    $('#notes')[0].addEventListener('input', function() {
        // dont enable saving for the original page, if boxes were highlighted.
        if (! (page_details['mod_id'] == 0 & edit_history.length > 0)) {
            document.getElementById("save_button").disabled = false;
        }
    }, false);
}

function loadArticleState() {
}
