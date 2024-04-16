// Identifies and navigates between regions of interest on a page 
// (as determined by the keyword-containing lines on the page).
class ViewNavigator {
  current_view_id = -1; // the current view in the viewmanager
  max_memory_usage = Math.round(250000000 / 100); // in bytes
  // NOTE ^^this^^ is really more of just an eyeballed number than an actual memory limit.
  // ^^^ TODO update calculation / memory ceiling for using uint16 instead of 8.
  viewpoints = []; // list of { 'total_value' : val, 'view_rect' : Rect } for each viewpoint.
  view_width; // in VIEWER POINTS
  view_height;
  viewer; // The OSD viewer object.

  sensible_view_width = 0.42244940914160234 * 0.7;
  sensible_view_height = 0.3867070024558195 * 0.7;
  ARR_FILL_VALUE = 0;

  constructor(viewer, kl_stats, view_width = null, view_height = null) {
    // view_width/height should be in viewer POINTS, not PIXELS.
    // See: 
    //   https://openseadragon.github.io/examples/viewport-coordinates/

    this.viewer = viewer
    this.keyline_stats = kl_stats;
    if (view_width == null) {
      this.view_width = this.sensible_view_width;
    } else {
      this.view_width = view_width;
    }
    if (view_height == null) {
      this.view_height = this.sensible_view_height;
    } else {
      this.view_height = view_height;
    }

    // Call calculateViews.
    this.calculateViews();
  }

  depthwiseArraySum(the_array) {
    // the_array should be a numjs ndarray.
    //
    the_array = the_array.tolist();

    var height = the_array.length;
    var width = the_array[0].length;
    var depth = the_array[0][0].length;

    const gpu = new GPU({ mode: 'gpu' });

    const sumChannels = gpu.createKernel(function(src_arr) {
      // Sum along the z axis
      //
      // src_arr: 3D ndarray.

      var sum = 0;
      for (let i = 0; i < this.constants.depth; i++) {
        sum += src_arr[this.thread.y][this.thread.x][i];
      }

      return sum;
    })
      .setOutput({ x : width, y : height})
    .setConstants({
      depth : depth
    });
    


    var result_map = sumChannels(the_array);

    result_map = nj.array(result_map)

    return result_map;
  }

  insertGaussian(values_arr, kl_idx, row_start, row_end, col_start, col_end, max_val) {
    // Insert a 2D gaussian in the region specified.
    //
    // params:
    //  values_arr:  the 3d array to modify.
    //  kl_idx:  the dept of the array at which to insert the gaussian.
    //  row/col_start/end: the region in which to insert gaussian.
    //  max_val:  the max value of the gaussian.
    //
    // returns:  the modified values_arr.
    //
    // TODO NOTE:  COULD MAKE THIS ALL SLICKER by moving EVERYTHING to GPU.
    //   I.e.:  instead of creating a value map for each layer and then summing,
    //     We could just iterate over every x,y in the map, and DETERMINE its value
    //     by computing the value of the gaussian at that point, for each keyline.
    //     (To make that even faster, we would only compute gaussian value when x,y falls
    //     within the region defined by row/col_start/end.)
    //     
    //     So, we'd first compute, for EACH KEYLINE, the parameters shown here for insertGaussian.
    //
    //     Then we'd do the current while loop:
      //     Then we'd compute value map on the GPU.
      //     Pick max, and remove keylines we've covered.
    var amplitude = max_val * 100; // NOTE *100 to make better use of integer space.

    var region_width = col_end - col_start;
    var region_height = row_end - row_start;

    var x0 = Math.round(col_start + (region_width/2));
    var y0 = Math.round(row_start + (region_height/2));
    var sigmaX = .2 * region_width;
    var sigmaY = .2 * region_height;

    function getGaussVal(amplitude, x0, y0, sigmaX, sigmaY, x, y) {
      var exponent = -(
        ( Math.pow(x - x0, 2) / (2 * Math.pow(sigmaX, 2)))
        + ( Math.pow(y - y0, 2) / (2 * Math.pow(sigmaY, 2)))
      );
      return amplitude * Math.pow(Math.E, exponent);
    }

    for ( let col=col_start; col< col_end; col++) {
      for ( let row=row_start; row< row_end; row++) {
        var the_val = getGaussVal(amplitude, x0, y0, sigmaX, sigmaY, col, row);
        values_arr.set(row, col, kl_idx, the_val);
      }
    }

    return values_arr;
  }

  makeGaussian(num_rows, num_columns, max_val) {
    // Create a 2d gaussian in an array of the given dimensions.
    var amplitude = max_val;
    var x0 = Math.round(num_columns/2);
    var y0 = Math.round(num_rows/2);
    var sigmaX = .2 * num_columns;
    var sigmaY = .2 * num_rows;

    function getGaussVal(amplitude, x0, y0, sigmaX, sigmaY, x, y) {
      var exponent = -(
        ( Math.pow(x - x0, 2) / (2 * Math.pow(sigmaX, 2)))
        + ( Math.pow(y - y0, 2) / (2 * Math.pow(sigmaY, 2)))
      );
      return amplitude * Math.pow(Math.E, exponent);
    }

    var arr = nj.zeros([num_rows, num_columns]);
    for ( let col=0; col< arr.shape[0]; col++) {
      for ( let row=0; row< arr.shape[1]; row++) {
        var the_val = getGaussVal(amplitude, x0, y0, sigmaX, sigmaY, col, row);
        arr.set(row, col, the_val)
      }
    }

    return arr;
  }


  plotValuesArr(arr, anchor_element_id, kl_id) {
    // Plotly plot the array, placing it at the anchor element.
    // 
    // If this is a 3D array, plot each layer separately.
    var anchor_el = document.getElementById(anchor_element_id);

    var subplot_data = [];
    var is_3d = false;
    var depth;
    if (arr[0][0].length) {
      depth = arr[0][0].length;
    } else {
      depth = 1;
    }
    for (let i=0; i < depth; i++) {
      subplot_data.push([]);
    }

    // Make a list of points:
    var x = [];
    var y = [];
    var val = [];

    var num_rows = arr.length;
    var num_cols = arr[0].length;
    for ( let col=0; col< num_cols; col++) {
      for ( let row=0; row< num_rows; row++) {
        x.push(col);
        y.push(num_rows - row);

        for (let i = 0; i < depth; i++){
          if (depth > 1) {
            subplot_data[i].push(arr[row][col][i]);
          } else {
            subplot_data[i].push(arr[row][col]);
          }
        }
        //val.push(arr[col][row]);
      }
    }

    var plot_data = []
    for (let i = 0; i < depth; i++) {
      plot_data.push(
        {
          //z: [[1, 20, 30], [20, 1, 60], [30, 60, 1]],
          x : x, y : y, z : subplot_data[i],
          xaxis: 'x' + (i + 1),
          yaxis: 'y' + (i + 1),
          type: 'heatmap'
        });
    }

    var title;
    if (depth == 1 && kl_id) {
      title = 'plotting value map for ' + kl_id;
    } else {
      title = 'plotting ' + depth + ' layers of value map';
    }

    var layout = {
        title: title,
      grid: {rows : Math.ceil(Math.sqrt(depth)), columns : Math.ceil(Math.sqrt(depth)), pattern: 'independent' },
        autosize: false,
        width: arr[0].length,
        height: arr.length
        };

    Plotly.newPlot(anchor_el, plot_data, layout);
  }

  calculateViews() {
    // Compute VALUE of each keyline.
    var kl_values = [];
    for (var kl_id in this.keyline_stats) {
      kl_values.push({ 'kl_id' : kl_id,
        'value' : this.calculateKeylineValue(kl_id)
      });
    }

    // calc scale factor based on max_memory_usage.
    //  NOTE scale_factor = min(1, scale factor)
    var imw_px = this.viewer.tileSources[1].levels[0].width;
    var imh_px = this.viewer.tileSources[1].levels[0].height;
    var num_kls = Object.keys(this.keyline_stats).length; // eww, javacsript
    var scale_factor = Math.sqrt((this.max_memory_usage / num_kls) / (imw_px * imh_px));

    // array with dimensions scaled based on scale_factor. 
    // Its third dimension == the number of keylines.
    var s_height = Math.floor(imh_px * scale_factor);
    var s_width = Math.floor(imw_px * scale_factor); // cols
    var values_arr = nj.zeros([s_height, s_width, num_kls], 'int16');

    // FOR EACH KEYLINE:
    var kl_idx = 0;
    var plot_data = []; // The subplot data for each layer.
    for (var kl_id in this.keyline_stats) {
      // Get the extrema of the keyline's overlay:
      var kl_rect_pt = this.viewer.getOverlayById(kl_id).getBounds(this.viewer.viewport);
      var min_x_pt = kl_rect_pt.x;
      var min_y_pt = kl_rect_pt.y;
      var max_x_pt = kl_rect_pt.x + kl_rect_pt.width;
      var max_y_pt = kl_rect_pt.y + kl_rect_pt.height;

      //  Get the point in "coverage space" for this keyline:
      var new_max_x_pt = min_x_pt + (this.view_width / 2); 
      var new_max_y_pt = min_y_pt + (this.view_height / 2);
      var new_min_x_pt = max_x_pt - (this.view_width / 2);   
      var new_min_y_pt = max_y_pt - (this.view_height / 2);

      //// TODO DEBUG visualizing coverage space on page:
      //var elt1 = document.createElement("div");
      //elt1.id = 'testydoo_'+kl_id;
      //elt1.classname = 'kw_highlight priority3';
      //var b1 = new OpenSeadragon.Rect(new_min_x_pt, new_min_y_pt, new_max_x_pt - new_min_x_pt, new_max_y_pt - new_min_y_pt, 0);
      //this.viewer.addOverlay({
      //    element: elt1,
      //    location:  b1
      //});

      //  Fill in relevant layer of array with the value of that keyline
      //    NOTE might want to use distance transform so that we prioritize centered views.
      //  
      //  First, convert from viewport coordinates to rows+columns in the array:
      var top_left_arr = this.scaledPixelsFromPoint(new OpenSeadragon.Point(new_min_x_pt, new_min_y_pt), scale_factor);
      var bottom_right_arr = this.scaledPixelsFromPoint(new OpenSeadragon.Point(new_max_x_pt, new_max_y_pt), scale_factor);
      var num_rows = values_arr.shape[0];
      var num_cols = values_arr.shape[1]; // width
      var row_start = Math.max(0, top_left_arr.y);
      var row_end = Math.min(num_rows, bottom_right_arr.y);
      var col_start = Math.max(0, top_left_arr.x);
      var col_end = Math.min(num_cols, bottom_right_arr.x);

      // If the keyline is wider / taller than the viewport, then swap the start and end idxs
      if (row_end < row_start) {
        var temp = row_start;
        row_start = row_end;
        row_end = temp;
      }
      if (col_end < col_start) {
        var temp = col_start;
        col_start = col_end;
        col_end = temp;
      }

      var the_value = kl_values[kl_idx]['value'];

      values_arr = this.insertGaussian(values_arr, kl_idx, row_start, row_end, col_start, col_end, the_value);

      // Print the max value in the layer of the array for that keyline:

      kl_idx++;
    }

    // In the while loop, need to convert the viewport dimensions from POINTS to PIXELS.
    var viewport_dim_pt = new OpenSeadragon.Point(this.view_width, this.view_height);
    var view_dims_px = this.viewer.viewport.pixelFromPointNoRotate(viewport_dim_pt);
    var view_width_px = view_dims_px.x;
    var view_height_px = view_dims_px.y;

    // do the main loop, greedily choosing the lowest value view-point,
    // until our viewpoints include every keyline.
    var num_covered = 0; // number of keylines covered by the views found so far.
    var kernel = nj.ones([1, 1, num_kls], 'int16');
    var num_iters = 0;
    while (num_covered < num_kls && num_iters < 20) {
      //this.plotValuesArr(values_arr.tolist(), 'ui_container');

      var total_view_value = this.depthwiseArraySum(values_arr);

      // Find the min value:
      // C'mon numjs, there's gotta be a better way:
      var max_val_row; 
      var max_val_col; 
      var max_val = -Infinity;
      //for (var i=0; i < total_view_value.shape[0]; i++) {
      for (var i=0; i < total_view_value.shape[0]; i++) {
        for (var j=0; j < total_view_value.shape[1]; j++) {
          if (total_view_value.get(i,j) > max_val) {
            max_val = total_view_value.get(i,j);
            max_val_col = j;
            max_val_row = i;  // this sucks where is my meshgrid ;-;

          }
        }
      }

      // Add view to the list
      var row_rescaled = max_val_row / scale_factor;
      var col_rescaled = max_val_col / scale_factor;
      var view_center_px = new OpenSeadragon.Point(col_rescaled, row_rescaled);
      var view_center_pt = this.viewer.world.getItemAt(0).imageToViewportCoordinates(view_center_px);
      // From center point to corner point:
      var view_corner_x_pt = view_center_pt.x - (this.view_width / 2);
      var view_corner_y_pt = view_center_pt.y - (this.view_height/ 2);
      var view_rect_pt = new OpenSeadragon.Rect(view_corner_x_pt, view_corner_y_pt, 
        this.view_width, this.view_height);

      this.viewpoints.push( {
        'total_value' : max_val,
        'view_rect' : view_rect_pt,
      });

      // Identify which keylines are covered by this viewpoint.
      // Update num_covered and neutralize their layers in values_arr.
      //
      // This is a 1x1x(num_keylines) array.
      var viewpoint_values = values_arr.slice([max_val_row, max_val_row+1], [max_val_col, max_val_col+1], [null]);
      viewpoint_values = viewpoint_values.reshape(viewpoint_values.shape[2]);
      for (var kl_idx=0; kl_idx < viewpoint_values.size; kl_idx++) {
        if (viewpoint_values.get(kl_idx) != this.ARR_FILL_VALUE) {
          // clear the corresponding layer in values_arr.
          values_arr.slice([null],[null],[kl_idx, kl_idx+1]).assign(this.ARR_FILL_VALUE, false);
          num_covered++;
        }
      }

      num_iters ++;
    }
  }

    scaledPixelsFromPoint(point, scale_factor) {
      // Take a Point in the viewpoint, and return the corresponding row, col in the 
      // SCALED view map.
      //
      // point: OpenSeadragon.Point instance.

      // Convert to viewport pixels.
      var point_in_pixels = this.viewer.world.getItemAt(0).viewportToImageCoordinates(point);

      // Scale pixels and round to int.
      point_in_pixels.x = Math.round(point_in_pixels.x * scale_factor);
      point_in_pixels.y = Math.round(point_in_pixels.y * scale_factor);

      return point_in_pixels;
    }

  calculateKeylineValue(kl_id) {
    // TODO Oy vey, should make more important keywords have HIGHER priority rather than lower.
    // But here we are.  So
    // Right now priority values range from 3 to 5.  Unless they're -1 (TODO will have to watch for that).
    // So, should say, 6 - value, so lowest priority has value 1, and highest has value 3.
    //kl_id is the id in this.keyline_stats 
    var kl_stats= this.keyline_stats[kl_id]

    // Linear combination of priority numbers and num_occurrences.
    // We square the keyword value to give high-priority kw's disproportionate weight.
    var total_value = 0;
    for (var kw_id in kl_stats) {
      total_value += kl_stats[kw_id][0] * ((6 - kl_stats[kw_id][1])**2); // TODO Must update 6 as max priority number grows.
    }

    return total_value
  }

  nextView() {
    // move to the next view.
    // NOTE actually moving the viewer should be done in the main script.
    if ((this.current_view_id == -1) || (this.current_view_id == this.viewpoints.length - 1)) {
      this.current_view_id = 0;
    } else {
      this.current_view_id += 1;
    }

    return this.viewpoints[this.current_view_id];
  }

  prevView() {
    // move to the previous view.
    // updates current_view_id and returns the new view's rectangle.
    // NOTE actually moving the viewer should be done in the main script.
    if ((this.current_view_id == -1)){
      this.current_view_id = 0;
    } else if (this.current_view_id == 0) {
      this.current_view_id = this.viewpoints.length - 1;
    }else {
      this.current_view_id -= 1;
    }

    return this.viewpoints[this.current_view_id];
  }

  get current_view() {
    // Get the view rectangle for the current view.
    if (this.current_view_id == -1) {
      return null;
    } else {
      return this.viewpoints[this.current_view_id];
    }
  }
}



