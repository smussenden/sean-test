/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
/* Functions for the summary stats dashboard */
/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
function init_summary_stats_dashboard() {
  // Create the plotly plots.
  update_annotations_per_user_chart(num_annotations_per_user, num_unique_pages_annotated_per_user, users_dict);
  //$('#numPagesAnnotatedPerUserDiv').show();
  $('#numUniquePagesAnnotatedPerUserDiv').show();
  update_pages_going_to_dataset_counter(num_pages_going_to_the_dataset);
  $('#numPagesInDatasetDiv').show();
}

function update_main_progress_bar(num_pages_annotated, num_pages_total) {
  // Update the bootstrap progress bar

  var annotation_progress = Math.round(100 * num_pages_annotated / num_pages_total);
  var annotation_progress_str = annotation_progress + '%';
  var num_pages_left = num_pages_total - num_pages_annotated;
  var num_pages_left_str = num_pages_left + ' pages left to annotate';

  // Update the progress bar:
  $('#mainProgressBar .progress-bar').css('width', annotation_progress_str);
  $('#mainProgressBar .progress-bar').attr('aria-valuenow', num_pages_annotated);
  $('#mainProgressBar .progress-bar').text(num_pages_annotated + ' pages annotated');
  // Update pages left to annotate
  $('#mainProgressBar .progress-bar-striped').css('width', (100 - annotation_progress) + '%');
  $('#mainProgressBar .progress-bar-striped').attr('aria-valuenow', num_pages_left);
  $('#mainProgressBar .progress-bar-striped').text(num_pages_left_str);

}
function update_pages_going_to_dataset_counter(num_pages_going_to_the_dataset) {

  // TODO NEXT for now, implement as simple counter.
  // Later, make this a pie chart, where ALL unique annotations are represented, with a breakdown of
  // how many pages are going to the dataset, vs pages with one or more flags...
  // Also have counters/percentages for the number of pages with each flag.
  $('#numPagesInDatasetDiv h4').text('Number of pages with article annotations for the dataset:  ' + num_pages_going_to_the_dataset);
}

function update_annotations_per_user_chart(annotations_per_user, unique_annotations_per_user, users_dict) {
  // Updates the pie chart.
  // 
  // params:
  //    annotations_per_user: dict of user_id -> num_annotations
  //    users_dict:  array of user dicts { id, name }

  //values_list = [];
  //labels_list = [];
  //for (var user_id in annotations_per_user) {
  //  user_id = parseInt(user_id);
  //  values_list.push(annotations_per_user[user_id]);

  //  if (user_id == 0) {
  //    labels_list.push('Unknown');
  //  } else if (user_id in users_dict) {
  //    console.log(user_id);
  //    console.log(users_dict);
  //    labels_list.push(users_dict[user_id].name);
  //  } else {
  //      console.log('ERROR:  user_id ' + user_id + ' not in users_dict');
  //  }
  //}

  //// Show the values, not the percentages
  //var data = [{
  //  values: values_list,
  //  labels: labels_list,
  //  type: 'pie',
  //  textinfo: 'value',
  //}];

  //// Plot has label "Annotations per user"
  //// The label has alt text:
  ////  'This plot shows the total number of annotations per user.  This INCLUDES DUPLICATES-- i.e.,
  ////  if a user has saved annotations for the same page multiple times, all of those annotations are counted.'
  //var layout = {
  //  title: 'Annotations per user',
  //  height: 400,
  //  width: 500
  //};

  //Plotly.newPlot('numPagesAnnotatedPerUserDiv', data, layout);

  // Now do the chart for unique pages per user:
  values_list = [];
  labels_list = [];
  for (var user_id in unique_annotations_per_user) {
    values_list.push(unique_annotations_per_user[user_id]);

    if (user_id == 0) {
      labels_list.push('Unknown');
    } else {
      labels_list.push(users_dict[user_id].name);
    }
  }

  // Show the values, not the percentages
  var data = [{
    values: values_list,
    labels: labels_list,
    type: 'pie',
    textinfo: 'value',
  }];

  // Plot has label "Annotations per user"
  // The label has alt text:
  //  'This plot shows the total number of annotations per user.  This INCLUDES DUPLICATES-- i.e.,
  //  if a user has saved annotations for the same page multiple times, all of those annotations are counted.'
  var layout = {
    title: 'UNIQUE annotations per user',
    height: 400,
    width: 500
  };

  Plotly.newPlot('numUniquePagesAnnotatedPerUserDiv', data, layout);
}

function update_summary_stats(data) {
  // data contains:
  //  'num_pages_annotated': num_pages_annotated,
  //  'num_annotations_per_user': num_annotations_per_user,
  //  'users_dict': users_dict,
  //  'num_pages_going_to_the_dataset': num_pages_going_to_the_dataset
  
  // Update the global vars:
  users_dict = data['users_dict'];
  num_pages_annotated = data['num_pages_annotated'];
  num_annotations_per_user = data['num_annotations_per_user'];
  num_unique_pages_annotated_per_user = data['num_unique_pages_annotated_per_user'];
  num_pages_going_to_the_dataset = data['num_pages_going_to_the_dataset'];
  // Make sure the keys of the dicts are integers:
  function convert_keys_to_integers(dict) {
    var new_dict = {};
    try {
      for (var key in dict) {
        if (key === undefined || key === "NaN") {
          continue;
        }
        new_dict[parseInt(key)] = dict[key];
      }
      return new_dict;
    } catch (err) {
      console.log('ERROR:  could not convert keys to integers');
      console.log(err);
      return null;
    }
  }
  num_annotations_per_user = convert_keys_to_integers(num_annotations_per_user);
  num_unique_pages_annotated_per_user = convert_keys_to_integers(num_unique_pages_annotated_per_user);

  if (num_annotations_per_user === null || num_unique_pages_annotated_per_user === null) {
    console.log('ERROR:  could not convert keys to integers for summary stats.');
    return;
  }
  
  // Update the stats dashboard:
  update_annotations_per_user_chart(num_annotations_per_user, num_unique_pages_annotated_per_user, users_dict);
  update_main_progress_bar(num_pages_annotated, num_original_pages);
  update_pages_going_to_dataset_counter(num_pages_going_to_the_dataset);
}

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
/* Functions to modify the DataTable: */
/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

// Only show annotations in the file browser:
function filterShowAnnotated() {
    // Steps:
    // - Change state of filter buttons.
    //<input class="form-check-input" type="radio" id="originalsFilter_hasAnnotationRadio" name="originalsFilterRadio">
    // Desired filter buttons state:
    //  - Annotations radio selected.  Originals deselected.
    //  - Has annotation, No annotation, and All are disabled.
    $('#annotationsRadio').prop('checked', true);
    $('#originalsRadio').prop('checked', false);
    $('#originalsFilter_hasAnnotationRadio').prop('disabled', true);
    $('#originalsFilter_noAnnotationRadio').prop('disabled', true);
    $('#originalsFilter_allRadio').prop('disabled', true);

    // - Call table.draw()
    $('#data').DataTable().draw();
}

// Only show non-annotated pages in the file browser:
function filterShowNonAnnotated() {
    // Steps:
    // - Change state of filter buttons.
    //   - Has annotation, No annotation, and All are enabled.
    console.log('filterShowNonAnnotated()');
    $('#annotationsRadio').prop('checked', false);
    $('#originalsRadio').prop('checked', true);
    $('#originalsFilter_hasAnnotationRadio').prop('disabled', false);
    $('#originalsFilter_noAnnotationRadio').prop('disabled', false);
    $('#originalsFilter_allRadio').prop('disabled', false);

    // - Call table.draw()
    $('#data').DataTable().draw();
}

function lock_row_for_client(file_id) {
  // Locks the row for the client.
  var row_instance = $('#data').DataTable().row(function (idx, data, node) {
    return data.file_id == file_id;
  });
  // If no row found for the file_id, return.
  if (row_instance.length == 0) {
    return;
  }
  // Set the locked col to true
  row_instance.data().locked = true;
  row_instance.cells().invalidate();

  // remove the link for the row by replacing the page_link column's content with
  //  the string 'link'
  row_instance.data().page_link = 'link';
  row_instance.cells().invalidate();
}

function unlock_row_for_client(file_id) {
  var row_instance = $('#data').DataTable().row(function (idx, data, node) {
    return data.file_id == file_id;
  });
  // If no row found for the file_id, return.
  if (row_instance.length == 0) {
    return;
  }
  // Set the locked col to false
  row_instance.data().locked = false;
  row_instance.cells().invalidate();

  // add the link for the row by replacing the page_link column's content with
  // the content of page_link_perma
  row_instance.data().page_link = row_instance.data().page_link_perma;
  row_instance.cells().invalidate();
}

function row_details_to_row_dict(row_details) {
    // drop any keys that are not in the columns list:
    var row_dict = {};
    //var column_names = $('#data').DataTable().settings().init().columns.map(function (col) {
    //    return col.data;
    //});
    var random_row = $('#data').DataTable().row(0).data();
    var column_names = Object.keys(random_row);
    console.log('column_names: ', column_names);
    for (var key in row_details) {
        if (column_names.includes(key)) {
            row_dict[key] = row_details[key];
        }
    }

    // Add the url attrs
    // page link 
    row_dict['page_link'] = '<a href="" onclick="openAnnotationPage(\'/pages/' + row_dict['file_id'] + '/' + row_dict['filepath'] + '/' + row_dict['mod_id']+ '\')">link</a>';
    //page_link_perma
    row_dict['page_link_perma'] = '<a href="" onclick="openAnnotationPage(\'/pages/' + row_dict['file_id'] + '/' + row_dict['filepath'] + '/' + row_dict['mod_id']+ '\')">link</a>';
    row_dict['edition'] = row_dict['edition'].slice(3,);
    row_dict['page'] = row_dict['page'].slice(4,);
    //row_dict['DEPRECATED'] = row_dict['num_annotations'] + row_dict['mod_id']; // Deprecated
    row_dict['notes'] = (row_dict['notes'].length > 40) ? row_dict['notes'].slice(0,40) : row_dict['notes'].slice(0,  row_dict['notes'].length);
  
  //// Last, must add placeholder empty array for annotation_entries.
  row_dict['annotation_entries'] = [];
  
  //// Verify that the table and the dict have all the same keys:
  //var table_columns = column_names;
  //var dict_keys = Object.keys(row_dict);
  //var found_inconsistency = false;
  //for (var i = 0; i < table_columns.length; i++) {
  //  if (!dict_keys.includes(table_columns[i])) {
  //    console.log('Error: table and dict have different keys.');
  //    found_inconsistency = true;
  //  }
  //}
  //for (var i = 0; i < dict_keys.length; i++) {
  //  if (!table_columns.includes(dict_keys[i])) {
  //    console.log('Error: table and dict have different keys.');
  //    found_inconsistency = true;
  //  }
  //}
  //if (found_inconsistency) {
  //  // Missing from table:
  //  var missing_from_table = dict_keys.filter(function (key) {
  //    return !table_columns.includes(key);
  //  });
  //  // Missing from dict:
  //  var missing_from_dict = table_columns.filter(function (key) {
  //    return !dict_keys.includes(key);
  //  });
  //  console.log('Missing from table: ', missing_from_table);
  //  console.log('MISSING FROM DICT: ', missing_from_dict);
  //  //throw new Error('The table and the dict have different keys!');
  //}

  return row_dict;
}

function update_row_for_client(row_details) {
  // Update the row in the client's table.
  //  NOTE: must handle TOP-LEVEL rows and CHILD-LEVEL rows differently.
  //  We need to search for all matching FILEPATHS and then find the result with the right FILE_ID.
  //  If necessary, search through the annotation_entries to find the right file_id.
  //
  //  params:
  //    row_details: dict of the row details.
  var row_dict = row_details_to_row_dict(row_details);

  var table = $('#data').DataTable();
  // Find matching filepath rows:
  var matching_rows = table.rows(function (idx, data, node) {
    return data.filepath == row_dict.filepath;
  });

  // Find the row with the matching file_id:
  for (var i = 0; i < matching_rows.length; i++) {
    var target_row = table.row(matching_rows[i]);
    if (target_row.file_id == row_dict.file_id) {
      var annotation_entries_bak = target_row.data().annotation_entries;
      target_row.data(row_dict);
      target_row.data().annotation_entries = annotation_entries_bak;
      target_row.cells().invalidate();
      break;
    } else {
      // Check the annotation_entries for the file_id:
      var annotation_entries = target_row.data().annotation_entries;
      for (var j = 0; j < annotation_entries.length; j++) {
        if (annotation_entries[j].file_id == row_dict.file_id) {
          delete row_dict.annotation_entries; // don't need if the row is itself an annotation entry.
          annotation_entries[j] = row_dict;
          target_row.cells().invalidate();
          break;
        }
      }
    }
  }
}


function add_row_for_client(row_details) {
  new_row = row_details_to_row_dict(row_details);

  // Get all existing rows with the same filepath.
  var existing_rows = $('#data').DataTable().rows(function (idx, data, node) {
    return data.filepath == new_row.filepath;
  });

  // Update the existing rows:
  for (var i = 0; i < existing_rows.data().length; i++) {
    var existing_row = existing_rows.data()[i];

    if (existing_row.mod_id == 0) {
      // CASE 1: existing_row is an ORIGINAL ROW (mod_id == 0): add new_row to its annotation_entries.
      // Iterate over the annotation_level_columns 
      var annotation_entry = {};
      for (var j = 0; j < annotation_level_columns.length; j++) {
        var col_name = annotation_level_columns[j];
        annotation_entry[col_name] = new_row[col_name];
      }
      
      // iterate over annotation entries.  If find new_row.mod_id, replace that annotation entry.
      var found = false;
      var found_idx = -1;
      for (var j = 0; j < existing_row.annotation_entries.length; j++) {
        if (existing_row.annotation_entries[j].mod_id == new_row.mod_id) {
          found = true;
          found_idx = j;
          break;
        }
      }

      if (found) {
        existing_row.annotation_entries[found_idx] = annotation_entry;
      } else {
        existing_row.annotation_entries.push(annotation_entry);
      }

      // Also update the last_modified time
      existing_row.last_modified = new_row.last_modified;
      existing_row.last_modified_by = new_row.last_modified_by;
      existing_row.last_modified_by_id = new_row.last_modified_by_id;
    }

    else {
      // CASE 2: existing_row is a page ANNOTATION (mod_id > 0).  Two sub-cases:
      //   1: new_row is a MODIFICATION of an EXISTING annotation.
      //   2: new_row is a NEW ANNOTATION.
      //
      // If new_row.mod_id is in the annotation_entries or is the same as the existing_row.mod_id,
      // then update the existing_row with the new_row.
      if (existing_row.mod_id == new_row.mod_id) {
        // CASE 2.1: this is a MODIFICATION of an EXISTING annotation.
        //   (and the main entry for this row is what needs updating)

        // Update the existing row with the new row.
        for (var key in new_row) {
          existing_row[key] = new_row[key];
        }
      } else {
        // CASE 2.1: this is a MODIFICATION of an EXISTING annotation.
        //   (and this mod_id is in the annotation_entries for this row)
        var row_in_annotation_entries = false;
        var row_idx_in_annotation_entries = -1;
        for (var j = 0; j < existing_row.annotation_entries.length; j++) {
          if (existing_row.annotation_entries[j].mod_id == new_row.mod_id) {
            row_in_annotation_entries = true;
            row_idx_in_annotation_entries = j;
            break;
          }
        }

        if (row_in_annotation_entries) {
          // Move existing_row into its annotation_entries.
          // Replace the existing_row's annotation_level_columns with the new_row's annotation_level_columns.
          var new_annotation_entry = {};
          for (var j = 0; j < annotation_level_columns.length; j++) {
            var col_name = annotation_level_columns[j];
            new_annotation_entry[col_name] = existing_row[col_name];
            existing_row[col_name] = new_row[col_name];
          }
          existing_row.annotation_entries.push(new_annotation_entry);
          // remove the old annotation entry for new_row. (row_idx_in_annotation_entries)
          existing_row.annotation_entries.splice(row_idx_in_annotation_entries, 1);
        }
        else {
          // CASE 2.2: this is a NEW ANNOTATION.
          // Annotation row (mod_id > 0): replace the annotation_level_columns of the existing row with
          // the new_row's annotation_level_columns.
          // Move the existing_row's annotation_entries to the new_row's annotation_entries.
          var existing_row_annotation_entry = {};
          for (var j = 0; j < annotation_level_columns.length; j++) {
            var col_name = annotation_level_columns[j];
            existing_row_annotation_entry[col_name] = existing_row[col_name];
            existing_row[col_name] = new_row[col_name];
          }
          new_row.annotation_entries.push(existing_row_annotation_entry);
        }
      }

      // Update num_annotations for all of the annotation_entries:
      var updated_num_annotations = existing_row['annotation_entries'].length;
      if (existing_row['mod_id'] != 0) {
        updated_num_annotations += 1;
      }
      for (var j = 0; j < existing_row.annotation_entries.length; j++) {
        existing_row.annotation_entries[j].num_annotations = updated_num_annotations;
      }

      // Update the existing row:
      existing_rows.data()[i] = existing_row;
    }
  }

  // Redraw the table:
  $('#data').DataTable().draw('full-hold');

  // Hide child rows if shown:
  for (var i = 0; i < existing_rows.data().length; i++) {
    // Check isShown() for each row:
    var target_row_idx = existing_rows[0][i];
    var target_row = existing_rows.row(target_row_idx);
    if (target_row.child.isShown()) {
      // Hide the child row:
      target_row.child.hide();
      target_row.toJQuery().removeClass('shown');
    }
      
  }

}

function remove_row_for_client(row_details) {
    // TODO set delete to true and hide the row.
    console.log('TODO delte not implemented');
}

function get_row_in_datatable(file_id) {
    table = $('#data').dataTable();
    var file_id_col_index = table.column('file_id:name').index();
    //var row_idx  = table.fnFindCellRowIndexes( file_id, file_id_col_index );  // Search file_id column
    // Use the rows api to find rows with this file_id:
    var row_idx = $('#data').DataTable().rows( function ( idx, data, node ) {
        return data.file_id == file_id;
    } ).indexes();

    row_idx = row_idx[0];
    //row = $('#data').DataTable().row(row_idx).data();
    return row_idx
}


function setupSocketIO() {
  // Message recieved from server
  socket.on('lock_page_for_client', function(data) {
    lock_row_for_client(data['file_id']);
  });

  socket.on('unlock_page_for_client', function(data) {
    unlock_row_for_client(data['file_id']);
  });

  socket.on('add_page_for_client', function(data) {
    add_row_for_client(data['page_details']);
  });

  socket.on('remove_page_for_client', function(data) {
    remove_row_for_client(data['file_id']);
  });

  socket.on('table_update', function(data) {
    updateTable(data);
  });

  socket.on('update_summary_stats', function(data) {
    update_summary_stats(data);
  });

  // Lock relevant rows at initial loading:
  var table = $('#data').DataTable();
  //var locked_col_index = table.column('locked:name').index();
  // Use rows api to find rows where data.locked == 'True' or data.locked == 'true'
  var locked_row_idxs = $('#data').DataTable().rows( function ( idx, data, node ) {
      return data.locked == true;
      //return data.locked == 'True' || data.locked == 'true';
  } );
  locked_row_idxs.data().each( function (row_data) {
    lock_row_for_client(row_data.file_id);
  });

  // Request an updated table state from server every N seconds
  update_interval_id = window.setInterval(requestTableStateUpdate, 2000);
}

function delayTableStateUpdate() {
    // delay requesting a table state update for n seconds.
    // Should fire when user clicks on an annotation page link,
    // So that the server has time to register the annotaiton page's new session
    window.clearInterval(update_interval_id);
    update_interval_id = window.setInterval(requestTableStateUpdate, 2000);
}

function requestTableStateUpdate() {
  // Request an updated table state from server

  // Get file_id's for locked rows:
  var table = $('#data').DataTable();
  var locked_col_index = table.column('locked:name').index();
  //var locked_rows_idxs = $('#data').dataTable().fnFindCellRowIndexes( 'True', locked_col_index );  // Search file_id column
  // Do the above using row api
  var locked_row_idxs = $('#data').DataTable().rows( function ( idx, data, node ) {
      return data.locked == true;
  } );

  //var locked_rows_idxs_also = $('#data').dataTable().fnFindCellRowIndexes( 'true', locked_col_index );  // Search file_id column
  //locked_rows_idxs = locked_rows_idxs.concat(locked_rows_idxs_also);
  var locked_row_ids = [];
  locked_row_idxs.data().each( function (row_data) {
    locked_row_ids.push(row_data.file_id);
  });
  ///locked_row_idxs.forEach( function (row_idx) {
  ///  // Get the file_id cell
  ///  var cell = $('#data').DataTable().cell(row_idx, 'file_id:name');
  ///  locked_row_ids.push(cell.data());
  ///});

  ret = {'last_updated' : last_update_time, 
    'rows_locked' : locked_row_ids };

  socket.emit('get_table_state_update', ret);
}

function updateTable(data) {
    // update table based on rows_to_update.
    // modify values as needed.
    // if deletion column state changes, call delete_col function.
    //
    // add any rows which aren't currently in the table.
    
    // update table based on list of locked rows.
    // unlock those rows.
    //console.log('I got this update!');
    //console.log(data);
  
    // if the table hasn't loaded yet, skip the update
    if ($('#data').DataTable().row(0).data() === undefined) {
      console.log('table not loaded yet, skipping update');
      return;
    }

    data['rows_to_update'].forEach(function (row) {
      var table_row_instance = $('#data').DataTable().row(function (idx, data, node) {
        return data.file_id == row['file_id'];
      });
        if (table_row_instance.index() === undefined) {
            console.log('adding');
            console.log(row);
            add_row_for_client(row);
        }
        else {
          console.log('update row for client');
          console.log(row);
          update_row_for_client(row);
        }
    });
    data['rows_to_unlock'].forEach(function (f_id) {
        console.log('unlocking ' + f_id);
        unlock_row_for_client(f_id);
    });
    data['rows_to_lock'].forEach(function (f_id) {
        console.log('locking ' + f_id);
        lock_row_for_client(f_id);
    });

    last_update_time = data['update_timestamp'];
}

function setUser(user_id) {
    var user = users_dict[user_id];
    if (user.id === 0) {
        return;
    }

    // called when user clicks a button in the usernames modal, userModal.
    // set the user for this session (emit to server)
    socket.emit('set_user', {'user_id' : user.id});

    // replace the login prompt in the header with the user's name:
    // hide logInAlert, show loggedInText, and replace the text in userNameSpan with the user's name.
    $('#logInAlert').hide();
    $('#userNameSpan').text(user.name);
    $('#loggedInText').show();

    // Set session_user to the new user:
    session_user = user;

   // // Update the hyperlinks in the table, adding the user_id as an arg to the url.
  ////  If there's already a user_id arg, replace it.
   // console.log('updating links');
   // $('#data').DataTable().rows().every( function (rowIdx, tableLoop, rowLoop) {
   //     var data = this.data();
   //     var url_shown = data[2]; // only hyperlink if the page is not currently opened.
   //     var url_perma = data[3];

   //   // Append or replace the user_id arg in the url:
   //     if (url_perma.indexOf('user_id') == -1) {
   //         url_perma = url_perma + '?user_id=' + user.id;
   //     }
   //     else {
   //         url_perma = url_perma.replace(/user_id=\d+/, 'user_id=' + user.id);
   //     }
   //   // Append the user_id to url_show IFF it is a hyperlink.
   //     if (url_shown.indexOf('http') != 0) {
   //       url_shown = url_perma;
   //     } // else the link is disabled bc it's open.

   //   // Apply the changes to the table, for both rows:
   //   data[2] = url_shown; data[3] = url_perma;
   //   this.data(data).draw();
   // });
   // console.log('finished updating links');

    //// close the modal.
    //$('#userModal').modal('hide');
}

function openAnnotationPage(path) {
  // Open the annotation page in a new tab.
  // Append all necessary args to the url.
  delayTableStateUpdate();

  // Append user id arg to url:
  var user_id = session_user.id;
  path = path + '?user_id=' + user_id;

  // Open the page in a new tab:
  window.open(path, '_blank');
}

var socket;
function setupJS() {
    $(document).ready(function() {
        // Set up the summary stats dashboard:
        init_summary_stats_dashboard();

         filterShowNonAnnotated();
        // TODO NOTE The http vs. https is important. Use http for localhost!
        // So, we check if we're on localhost, and if so, use http.
        // Otherwise, use https.
        var url = new URL(window.location.href);
        var connection_domain_prefix = 'https://';
        if (url.hostname == 'localhost' || url.hostname == '127.0.0.1') {
            connection_domain_prefix = 'http://';
            console.log("Dev mode. Using http with socketio");
        }
        socket = io.connect(connection_domain_prefix + document.domain + ':' + location.port);

        setupSocketIO();
    });
}
