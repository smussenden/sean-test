// manages a SINGLE article box in the articles_sidebar.
class Article {
  id; //  number 0-9 identifying this article.
  overlays; //  list of overlay objects (see OpenSeaDragon documentation) which belong to this article.
  article_box; //  the article_box DOM element for this article in the articles_sidebar.
  my_color;

  constructor(id, overlay_ids = []) {
  // Color for each article ID:
  this.highlight_colors = [
        "rgb(47, 79, 79, 0.5)",
        "rgb(139, 69, 19, 0.5)",
        "rgb(34, 139, 34, 0.5)",
        "rgb(75, 0, 130, 0.5)",
        "rgb(255,255,0, 0.5)",
        "rgb(0,255,255, 0.5)",
        "rgb(255,0,255, 0.5)",
        "rgb(238, 232, 170, 0.5)",
        "rgb(100, 149, 237, 0.5)",
        "rgb(255, 105, 180, 0.5)"
  ];

  this.border_colors = [
        "rgb(47, 79, 79)",
        "rgb(139, 69, 19)",
        "rgb(34, 139, 34)",
        "rgb(75, 0, 130)",
        "rgb(255,255,0)",
        "rgb(0,255,255)",
        "rgb(255,0,255)",
        "rgb(238, 232, 170)",
        "rgb(100, 149, 237)",
        "rgb(255, 105, 180)"
    ];
    this.overlays = [];
    
    this.id = parseInt(id);
    
    this.article_box = document.getElementById('article_box_' + id);

    //  Clear any rows in the tabs list
    $('#article_box_' + id + ' .article_tab').remove();
    //this.article_box.style.display = 'none';

    this.setState(overlay_ids);

    this.my_color = this.highlight_colors[this.id];
    this.my_border_color = this.border_colors[this.id];

  }

  removeOverlay(o_id) {
    var removed = false;
    var found_overlay = false;
    var idx = 0;

    var overlay_to_remove;
    //this.overlays.forEach( function(o) {
    for (let o in this.overlays) {
      o = this.overlays[o];
      if (o.element.id == o_id) {
        overlay_to_remove = o;
        this.overlays.splice(idx, 1);
        removed = true;
        found_overlay = true;
        break;
      }
      else {
        idx += 1;
      }
    }

    // Update UI:
    //  change overlay's color
    if (found_overlay) {
      overlay_to_remove.element.style.backgroundColor = 'transparent';
      overlay_to_remove.element.style.borderColor = $('.highlight').css("borderColor");
    }
    
    //  remove row from article_box list of tabs
    var old_tab = document.getElementById('article_tab_' + o_id);
    console.log('looked for old tab w id: ' + 'article_tab_' + o_id);
    console.log(old_tab);
    old_tab.remove();

    //  IF article box no longer contains tabs, hide it.
    if (this.overlays.length == 0) {
      this.article_box.style.display = 'none';
    }
    
    return removed;
  }

  addOverlay(o_id) {
    // Add overlay object to this.overlays

    var overlay = myDragon.getOverlayById(o_id);
    this.overlays.push(overlay);

    var overlay = null;
    myDragon.overlays.every( function (o) {
      if (o.id == o_id) {
        overlay = o;
        return false;
      } else {
        return true;
      }
    });
    overlay = document.getElementById(o_id);
    
    console.log('Looking for o_id ' + o_id + ', we found overlay: ');
    console.log(overlay);
    // Update UI:
    //  change overlay's color
    overlay.style.backgroundColor = this.my_color;
    overlay.style.borderColor = this.my_border_color;

    //  add row to article_box list of tabs
    var new_tab = document.createElement('div');
    new_tab.className = 'article_tab';
    new_tab.id = 'article_tab_' + o_id;
    new_tab.innerHTML = overlay.id;

    //  IF article box is currently invisible, then show it!
    var the_el = $('#' + this.article_box.id).children('#home-collapse')[0];
    the_el.appendChild(new_tab);
    this.article_box.style.display= 'block';
    //  (optional:  assign callbacks for highlighting overlay when moused over)
  }

  setState(overlay_ids) {
    // (overwrite existing this.overlays)
    // add overlays objects to this.overlays.
    overlay_ids.forEach( function (o_id) {
      this.addOverlay(o_id);
    });
  }

  getState() {
    // get overlay_id for each overlay in this.overlays
    overlay_ids = [];
    this.overlays.forEach( function (o) {
      overlay_ids.push(o.id);
    });

    return overlay_ids;
  }

  toggleSidebarHighlight(activate_highlight) {
    if (activate_highlight) {
      this.article_box.className = 'article_box_highlighted';
    } else {
      this.article_box.className = 'article_box';
    }

  }

  get id() {
    return this.id;
  }

  get overlays() {
    return this.overlays;
  }
  
  get articleBox() {
    return this.article_box;
  }
}

// Manages the article membership of the overlay boxes on the page.
class ArticleManager {

  sidebar; // DOM element for the articles_sidebar.
  articles;

  overlay_membership; // Dict mapping overlay id to articles.

  constructor(articles_by_overlay_id = [], article_sidebar_id = 'articles_sidebar') {
    this.overlay_membership = {};
    this.articles = [
    new Article(0),
    new Article(1),
    new Article(2),
    new Article(3),
    new Article(4),
    new Article(5),
    new Article(6),
    new Article(7),
    new Article(8),
    new Article(9)
  ];

    this.sidebar = document.getElementById(article_sidebar_id);

    this.setState(articles_by_overlay_id);
  }

  articleFromOverlayID(overlay_id) {
    // query #overlay_membership to get the ID of this overlay's article. 

    var art_id = this.overlay_membership[overlay_id];

    if (art_id === undefined ) {
      return -1;
    } else {
      return this.articles[art_id];
    }
  }

  addOverlayToArticle(overlay_id, article_id) {
    // - check #overlay_membership to get current membership
    //    if is already a member, then remove it from that article:
    if (this.overlay_membership.hasOwnProperty(overlay_id)) {
      this.removeHighlight(overlay_id);
      delete this.overlay_membership[overlay_id];
    }

    // - add it to the article: 
    this.articles[article_id].addOverlay(overlay_id);
    //  - update overlay_membership
    this.overlay_membership[overlay_id] = article_id;
  }

  removeOverlayFromArticle(overlay_id, article_id) {
    if (this.overlay_membership.hasOwnProperty(overlay_id)) {
      this.articles[article_id].removeOverlay(overlay_id);
      delete this.overlay_membership[overlay_id];
    }
  }

  removeHighlight(overlay_id) {
    // remove highlighted overlay from whatever article it's part of.
    var art_id = this.articleFromOverlayID(overlay_id).id;
    this.removeOverlayFromArticle(overlay_id, art_id);
  }

  setState(articles_by_overlay_id) {
    // params:
    //  articles_by_overlay_id:  dict mapping overlays to article_id's.
    Object.keys(articles_by_overlay_id).forEach( function(overlay_id) {
      // -1 = not part of an article.
      if (articles_by_overlay_id[overlay_id] != -1) {
       this.addOverlayToArticle(overlay_id, articles_by_overlay_id[overlay_id]);
      }
    }, this);
  }

  getState() {
    return this.overlay_membership;
  }

}

        

