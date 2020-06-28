var workers_table = null;
var queues_table = null;
var jobs_table = null;

var worker_status = {
    'idle': 'warning',
    'busy': 'success',
    'started': 'success',
    'suspended': 'danger',
}

function update_modal_info(modal, modal_title, attr_class, attr_name, attr_task, modal_body) {
    modal.find('.modal-title').text(modal_title)
    modal.attr('targetclass', attr_class)  // class like job, queue, worker
    modal.attr('name', attr_name)               // id
    modal.attr('task', attr_task)          // delete, requeueall etc
    modal.find('.modal-body').text(modal_body)
}

function modal_success(modal, response) {
    modal.find('.modal-title').html('<a href="#" class="btn btn-rounded btn-success">Success</a>');
    modal.find('.modal-body').html(response.message);
    modal.find('.modal-footer').hide();
}

function modal_error(modal, response) {
    flask_response = JSON.parse(response.responseText);
    modal.find('.modal-title').html('<a href="#" class="btn btn-rounded btn-danger">Error</a>');
    modal.find('.modal-body').html(flask_response.message + 
        `<span class="badge badge-pill badge-brand ml-1">` + response.statusText + `</span>
        <br>
        <div class="alert alert-danger mt-1 mb-2" style="white-space: pre-wrap" role="alert">`+flask_response.traceback+
        `</div>`
        );
    modal.find('.modal-footer').hide();
}

function refresh_dashboard() {
    if ($('#main_dashboard').has('#workers_table').length > 0 && workers_table != null) {
        workers_table.ajax.reload(null, false); // user paging is not reset on reload
    } else if ($('#main_dashboard').has($('#queues_table')).length > 0 && queues_table != null) {
        queues_table.ajax.reload(null, false); // user paging is not reset on reload
    } else if ($('#main_dashboard').has('#jobs_table').length > 0 && jobs_table != null) {
        jobs_table.ajax.reload(null, false); // user paging is not reset on reload
    }
}

function post_worker_suspend_resume(){
    current = $('#suspendresume').data('action')
    if(current == 'suspendall'){
        $('#suspendresume').data('action', 'resumeall');
        $('#suspendresume').text('Resume All Workers');
    }else{
        $('#suspendresume').data('action', 'suspendall');
        $('#suspendresume').text('Suspend All Workers');
    }
}

function ajax_action(request_type, action_url, _data, table, modal, post_success = undefined) {
    $.ajax({
        type: request_type,
        url: action_url,
        data: inject_globals(_data),
        dataType: "json",
        success: function (response) {
            modal_success(modal, response)
            // force refresh to update
            table.ajax.reload(null, false);
            setTimeout(function () {
                $('#confirmation').modal('hide');
            }, 2000);
            if (post_success !== undefined){
                post_success();
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            modal_error(modal, jqXHR);
        }
    });
}

function modal_restore() {
    // restore modal state on closing
    $("#confirmation").on("hidden.bs.modal", function () {
        $(this).find('modal-title').trigger('reset');
        $(this).find('name').trigger('reset');
        $(this).find('.modal-footer').show();
    });
}

function action_modal_onshow() {
    $('#confirmation').on('show.bs.modal', function (event) {
        var button = $(event.relatedTarget)             // Button that triggered the modal
        var target_class = button.data('targetclass')   // Extract job/queue/worker
        var target_id = button.data('id')               // Extract job id/ queue id/ worker id   
        var action = button.data('action')              // extract action like delete, cancel, requeueall 
        var modal = $(this)
        if (target_class === 'queue') {
            if (action === 'empty') {
                update_modal_info(modal, 'Confirm to empty ' + target_id, target_class, target_id, action, 'All valid jobs currently on queue will be removed from queue as well as from redis job namespace!')
            } else if (action === 'delete') {
                update_modal_info(modal, 'Confirm to delete ' + target_id, target_class, target_id, action, 'Queue will be deleted along with all jobs on it!')
            } else if (action === 'deleteall') {
                update_modal_info(modal, 'Confirm to delete these queues ' + get_checked_queues().join(", "), target_class, target_id, action, 'These queues will be deleted along with all jobs on it!')
            } else if (action === 'emptyall') {
                update_modal_info(modal, 'Confirm to empty these queues ' + get_checked_queues().join(", "), target_class, target_id, action, 'All the queued jobs will be removed from these queues!')
            }
        } else if (target_class === 'job') {
            var queue_for_job = button.data('jobqueue')
            if (action === 'requeue') {
                update_modal_info(modal, 'Confirm to requeue ' + target_id, target_class, target_id, action, 'Job will be removed from failed job registry and put on ' + queue_for_job)
            } else if (action === 'delete') {
                update_modal_info(modal, 'Confirm to delete ' + target_id, target_class, target_id, action, 'Job will be permanently deleted from Redis!')
            } else if (action === "cancel") {
                update_modal_info(modal, 'Confirm to cancel ' + target_id, target_class, target_id, action, 'Job will be cancelled and never be executed or inspected!')
            } else if (action === "cancelall") {
                update_modal_info(modal, 'Confirm to cancel all jobs on ' + get_checked_queues().join(", "), target_class, target_id, action, 'Jobs will be cancelled and never be executed or inspected!')
            } else if (action === "deleteall") {
                update_modal_info(modal, 'Confirm to delete all jobs on ' + get_checked_queues().join(", "), target_class, target_id, action, 'Jobs will be permanently deleted from Redis!')
            } else if (action === "requeueall") {
                update_modal_info(modal, 'Confirm to requeue all failed jobs from ' + get_checked_queues().join(", "), target_class, target_id, action, 'All failed jobs will be removed from their queue failed job registry and put on their respective original queues again')
            }
        } else if (target_class === 'worker') {
            if (action === 'delete') {
                update_modal_info(modal, 'Confirm to delete ' + target_id, target_class, target_id, action, 'Worker on same instance will be sent SIGINT to request warm shutdown, any currently executing tasks will be completed first.')
            } else if (action === 'deleteall') {
                update_modal_info(modal, 'Confirm to delete all workers', target_class, target_id, action, 'All workers on same instance will be sent SIGINT to request warm shutdown, any currently executing tasks will be completed first.')
            } else if(action == 'suspendall'){
                update_modal_info(modal, 'Confirm to suspend all workers', target_class, target_id, action, 'All workers will be suspended, no jobs will be executed now, any currently executing tasks will be completed first. Resume workers to make them work again.')                
            } else if(action == 'resumeall'){
                update_modal_info(modal, 'Confirm to resume all workers', target_class, target_id, action, 'All workers will be resumed and will start to work again.')                
            }
        }
    })
}

function get_checked_queues() {
    var queues = []
    $('.queuelistitem').each(function (index) {
        var active = $(this).find('input').prop("checked") ? 1 : 0;
        if (active) {
            queues.push($(this).find('label').text());
        }
    });
    return queues;
}

function get_checked_job_status() {
    var status = []
    $('.jobstatuslistitem').each(function (index) {
        var active = $(this).find('input').prop("checked") ? 1 : 0;
        if (active) {
            status.push($(this).find('label').text());
        }
    });
    return status;
}

function get_currently_selected_redis_index() {
    return $('#redis_instances').prop('selectedIndex');
}


function setup_queues_datatable(nunjucks_urls, site_map) {

    queues_table = $('#queues_table').DataTable({
        "processing": "True",
        "language": {
            "loadingRecords": "&nbsp;",
            "processing": "Loading...",
        },
        "ajax": {
            "url": site_map['rqmonitor.list_queues_api'],
            "type": "GET",
            "data": function (d) {
                return $.extend(
                    {}, d, inject_globals(),
                )
            },
            "dataSrc": "data",
            "dataType": "json",
            "error": function (jqXHR, textStatus, errorThrown) {
                $.get({
                    url: nunjucks_urls['error'],
                    cache: false
                }).then(function(error_template){
                    rendered_template = nunjucks.renderString(
                            error_template, 
                            { 
                                'error_info': JSON.parse(jqXHR.responseText),
                                'textStatus': textStatus,
                                'errorThrown': errorThrown,
                            }
                        );
                    $('#main_content').html(rendered_template);
                })
            }
        },
        "columns": [
            {
                data: "queue_name",
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        data = '<a href="#" data-toggle="modal" data-target=".bd-example-modal-lg">' + data + '</a>';
                    }
                    return data;
                },
                className: "queue_info_modal"
            },
            { data: "job_count" },
            {
                data: "action",
                width: "10%",
                render: function (data, type, row, meta) {
                    if (type == 'display') {
                        data =
                            `
                        <a href="#" class="btn btn-warning btn-block" data-action="empty"
                        data-toggle="modal" data-target="#confirmation" data-targetclass="queue" data-id="`+ row.queue_name + `">Empty</a>
                        <a href="#" class="btn btn-danger btn-block" data-action="delete"
                        data-toggle="modal" data-target="#confirmation" data-targetclass="queue" data-id="`+ row.queue_name + `">Delete</a>
                        `
                    }
                    return data;
                },
                defaultContent:
                    `
                    <a href="#" class="btn btn-warning btn-block" data-action="empty"
                    data-toggle="modal" data-target="#confirmation">Empty</a>
                    <a href="#" class="btn btn-danger btn-block" data-action="delete"
                    data-toggle="modal" data-target="#confirmation">Delete</a>
                `
            },

        ]
    });


}

function reload_sidebar_queues(site_map) {
    $.ajax({
        type: "GET",
        url: site_map['rqmonitor.refresh_sidebar_queues'],
        data: inject_globals(),
        success: function (response) {
            $('#sidebar_queues').html(response);
        },
        error: function (rs, e) {
            $('#sidebar_queues').html(`<strong>` + JSON.stringify(rs) + `</strong>`);
        }
    });
}

function refresh_redis_memory(url) {
    $('#redis_memory_value').html('');
    $.get({
        url: url,
        data: inject_globals(),
        cache: false
    }).then(function (data) {
        $('#redis_memory_value').text(data.redis_memory_used)
    });
}

function inject_globals(data) {
    if (data === undefined) {
        data = {}
    }
    return Object.assign(data,
        {
            'redis_instance_index': get_currently_selected_redis_index(),
        }
    );
}

function on_redis_instance_change(site_map) {
    $('#redis_instances').on('change', function () {
        refresh_dashboard();
        refresh_redis_memory(site_map['rqmonitor.redis_memory_api']);
        reload_sidebar_queues(site_map);
    })
}

function on_redis_memory_refresh(site_map){
    $('#redis_memory_refresh').on('click', function () {
        refresh_redis_memory(site_map['rqmonitor.redis_memory_api']);
    });
}

function setup_worker_datatable(nunjucks_urls, site_map) {
    workers_table = $('#workers_table').DataTable({
        "processing": "True",
        "language": {
            "loadingRecords": "&nbsp;",
            "processing": "Loading...",
        },
        "ajax": {
            "url": site_map['rqmonitor.list_workers_api'],
            "type": "GET",
            "data": function (d) {
                return $.extend(
                    {}, d, inject_globals(),
                )
            },
            "dataSrc": "data",
            "dataType": "json",
            "error": function (jqXHR, textStatus, errorThrown) {
                $.get({
                    url: nunjucks_urls['error'],
                    cache: false
                }).then(function(error_template){
                    rendered_template = nunjucks.renderString(
                            error_template, 
                            { 
                                'error_info': JSON.parse(jqXHR.responseText),
                                'textStatus': textStatus,
                                'errorThrown': errorThrown,
                            }
                        );
                    $('#main_content').html(rendered_template);
                })
            }
        },
        "columns": [
            {
                data: "worker_name",
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        data = `
                                <a href="#" data-toggle="modal" data-target="#infomodal"
                                data-worker="`+ data + `">` + data + `</a>
                                `;
                    }
                    return data;
                },
                className: "worker_info_modal"
            },
            { data: "listening_on" },
            {
                data: "status",
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        data = `<span class="badge badge-` + worker_status[data] + `">` + data + `</span>`;
                    }
                    return data;
                },
            },
            { data: "host_ip" },
            { data: "current_job_id" },
            { data: "failed_jobs" },
            {
                data: null,
                width: "10%",
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        data = `
                            <a href="#" class="btn btn-danger" data-toggle="modal" data-action="delete"
                            data-target="#confirmation" data-targetclass="worker" data-id="`+ row.worker_name + `"> Delete </a>
                            `;
                    }
                    return data;
                },
                className: "center",
                defaultContent: `
                                <a href="#" class="btn btn-danger" data-toggle="modal"
                                data-target="#confirmation"> Delete </a>
                                `,
            }
        ]
    });

    function show_worker_modal(site_map){
        $('#infomodal').on('show.bs.modal', function (event) {
            var button = $(event.relatedTarget); // Button that triggered the modal
            var worker_id = button.data('worker'); // Extract info from data-* attributes
            var modal = $(this);
    
            $.ajax({
                url: site_map['rqmonitor.worker_info_api'],
                data: { 'worker_id': worker_id},
                success: function (data) {
                    modal.find('.modal-title').text('Showing Info for ' + worker_id)
                    modal.attr('name', worker_id)
                    modal.find('#birth_date').text(data.worker_birth_date);
                    modal.find('#death_date').text(data.worker_death_date);
                    modal.find('#failed_job_count').text(data.worker_failed_job_count);
                    modal.find('#successful_job_count').text(data.worker_successful_job_count);
                    modal.find('#job_monitoring_interval').text(data.worker_job_monitoring_interval);
                    modal.find('#last_heartbeat').text(data.worker_last_heartbeat);
                    modal.find('#current_job_id').text(data.worker_current_job_id);
                    modal.find('#last_cleaned_at').text(data.worker_last_cleaned_at);
                    modal.find('#host_name').text(data.worker_host_name);
                    modal.find('#worker_ttl').text(data.worker_ttl);
                    modal.find('#result_ttl').text(data.worker_result_ttl);
                },
                error: function (rs, e) {
                    alert(rs.responseText);
                }
            });
        });
    }

    show_worker_modal(site_map);

    /*
    $('#workers_table tbody').on('click', '.worker_info_modal', function () {
      var row_clicked = workers_table.row($(this).parents('tr')).data();
      worker_id = Object.values(row_clicked)[0];
    });
    */
}

function setup_jobs_datatable(nunjucks_urls, site_map) {
    var job_result_ttl = "specifies how long (in seconds) successful jobs and their results are kept. Expired jobs will be automatically deleted. Defaults to 500 seconds.";
    var job_timeout = "specifies the maximum runtime of the job before it’s interrupted and marked as failed. Its default unit is seconds and it can be an integer or a string representing an integer(e.g. 2, '2'). Furthermore, it can be a string with specify unit including hour, minute, second (e.g. '1h', '3m', '5s').";
    var job_failure_ttl = " specifies how long (in seconds) failed jobs are kept (defaults to 1 year)";
    var job_ttl = "specifies the maximum queued time (in seconds) of the job before it’s discarded. This argument defaults to None (infinite TTL).";

    /*
    from flask and jinja2's perspective all templates to be rendered by nunjucks 
    can be considered as static files so kept in static folder and it also eases the 
    task of generating urls 
    */

    $.get({
        url: nunjucks_urls['job_info'],
        cache: false
    }).then(function (job_info_template) {
        jobs_table = $('#jobs_table').DataTable({
            "serverSide": "True",
            "pageLength": 50,
            "processing": "True",
            "language": {
                "loadingRecords": "&nbsp;",
                "processing": "Loading...",
            },
            "ajax": {
                "url": site_map['rqmonitor.list_jobs_api'],
                "type": "GET",
                // in case of reload if data is initialised as static object then will not
                //be evaluated only once. If you want to read new data on each reload, you'd need to use it as a
                //function. check @ comment at https://datatables.net/reference/api/ajax.reload()
                "data": function (d) {
                    return $.extend(
                        {}, d, inject_globals(), {
                        'queues': get_checked_queues(),
                        'jobstatus': get_checked_job_status(),
                    },
                    )
                },
                "dataSrc": "data",
                "dataType": "json",
                "error": function (jqXHR, textStatus, errorThrown) {
                    $.get({
                        url: nunjucks_urls['error'],
                        cache: false
                    }).then(function(error_template){
                        rendered_template = nunjucks.renderString(
                                error_template, 
                                { 
                                    'error_info': JSON.parse(jqXHR.responseText),
                                    'textStatus': textStatus,
                                    'errorThrown': errorThrown,
                                }
                            );
                        $('#main_content').html(rendered_template);
                    })
                }
            },
            "columns": [
                {
                    data: "job_info",
                    render: function (data, type, row, meta) {
                        if (type === 'display') {
                            //data = nunjucks.render("{{ url_for('static', filename='nunjucks/job_info.html') }}", data)
                            data = nunjucks.renderString(job_info_template, { 'job_data': data });
                        }
                        return data;
                    },
                    className: "worker_info_card_link"
                },
                {
                    data: "action",
                    width: "10%",
                    render: function (data, type, row, meta) {
                        if (type == 'display') {
                            // implement through nunjucks TODO
                            if (row.job_info.job_status === "failed") {
                                data =
                                    `
        <a href="#" class="btn btn-warning btn-block" data-action="requeue"
            data-toggle="modal" data-target="#confirmation" data-targetclass="job" data-id="`+ row.job_info.job_id + `" data-jobqueue="` + row.job_info.job_queue + `">Requeue</a>
        <a href="#" class="btn btn-danger btn-block" data-action="delete"
            data-toggle="modal" data-target="#confirmation" data-targetclass="job" data-id="`+ row.job_info.job_id + `" data-jobqueue="` + row.job_info.job_queue + `">Delete</a>
        `
                            } else {
                                data =
                                    `
        <a href="#" class="btn btn-warning btn-block" data-action="cancel"
            data-toggle="modal" data-target="#confirmation" data-targetclass="job" data-id="`+ row.job_info.job_id + `" data-jobqueue="` + row.job_info.job_queue + `">Cancel</a>
        <a href="#" class="btn btn-danger btn-block" data-action="delete"
            data-toggle="modal" data-target="#confirmation" data-targetclass="job" data-id="`+ row.job_info.job_id + `" data-jobqueue="` + row.job_info.job_queue + `">Delete</a>
        `
                            }
                        }
                        return data;
                    },
                    defaultContent:
                        `
    <a href="#" class="btn btn-warning btn-block">Requeue/Cancel</a>
    <a href="#" class="btn btn-danger btn-block">Delete</a>
    `
                },
            ]
        });

    });

}     

function action_modal_onconfirm(site_map) {
    $('#confirmation').on('click', '.confirm', function (event) {
        var target_class = $(this).closest('.modal').attr('targetclass');
        var target_id = $(this).closest('.modal').attr('name');
        var task = $(this).closest('.modal').attr('task');
        var modal = $(this).closest('.modal');

        modal.find('.modal-body').html('<span class="dashboard-spinner spinner-sm"></span>')

        if (target_class === 'queue') {
            if (task === 'empty') {
                ajax_action("POST", site_map['rqmonitor.empty_queue_api'], { 'queue_id': target_id}, queues_table, modal);           
            } else if (task === 'delete') {
                ajax_action("POST", site_map['rqmonitor.delete_queue_api'], { 'queue_id': target_id}, queues_table, modal);
                reload_sidebar_queues(site_map);
            } else if (task === 'deleteall') {
                ajax_action("POST", site_map['rqmonitor.delete_all_queues_api'],{}, queues_table, modal);
                reload_sidebar_queues(site_map);
            } else if (task === 'emptyall') {
                ajax_action("POST", site_map['rqmonitor.empty_all_queues_api'], {}, queues_table, modal);
            }
        } else if (target_class === 'job') {
            if (task === 'requeue') {
                ajax_action("POST", site_map['rqmonitor.requeue_job_api'], { 'job_id': target_id }, jobs_table, modal);
            } else if (task === "delete") {
                ajax_action("POST", site_map['rqmonitor.delete_job_api'], { 'job_id': target_id }, jobs_table, modal);
            } else if (task === "cancel") {
                ajax_action("POST", site_map['rqmonitor.cancel_job_api'],
                    { 'job_id': target_id },
                    jobs_table, modal);
            } else if (task === "deleteall") {
                ajax_action("POST", site_map['rqmonitor.delete_all_jobs_api'], {
                    'queues': get_checked_queues(),
                    'jobstatus': get_checked_job_status(),
                }, jobs_table, modal);
            } else if (task === "requeueall") {
                ajax_action("POST", site_map['rqmonitor.requeue_failed_jobs_api'], {
                    'queues': get_checked_queues(),
                    'jobstatus': get_checked_job_status(),
                }, jobs_table, modal);
            } else if (task === "cancelall") {
                ajax_action("POST", site_map['rqmonitor.cancel_queued_jobs_api'], {
                    'queues': get_checked_queues(),
                    'jobstatus': get_checked_job_status(),
                }, jobs_table, modal);
            }
        } else if (target_class === 'worker') {
            if (task === "delete") {
                ajax_action("POST", site_map['rqmonitor.delete_workers_api'], {
                    'worker_id': target_id,
                }, workers_table, modal);
            } else if (task === "deleteall") {
                ajax_action("POST", site_map['rqmonitor.delete_workers_api'], {
                    'delete_all': "true",
                }, workers_table, modal);
            } else if (task === "suspendall") {
                ajax_action("POST", site_map['rqmonitor.suspend_workers_api'], {
                }, workers_table, modal, post_worker_suspend_resume);
            } else if (task === "resumeall") {
                ajax_action("POST", site_map['rqmonitor.resume_workers_api'], {
                }, workers_table, modal, post_worker_suspend_resume);
            }
        }

    })
}

function on_job_status_selection_change(){
    $('#jobstatus').on('change', 'input[type="checkbox"]', function (event) {
        if (jobs_table != null) {
            jobs_table.ajax.reload(null, false);
        }
    });
}

function on_queue_selection_change(){
    $('#fromqueues').on('change', 'input[type="checkbox"]', function (event) {
        if (jobs_table != null) {
            jobs_table.ajax.reload(null, false);
        }
    });
}  

function on_click_jobs_dashboard(nunjucks_urls, sitemap){
    $('#jobsmenu').on('show.bs.collapse', function (e) {
        if ($(this).is(e.target)) {
            $.ajax({
                type: "GET",
                url: site_map['rqmonitor.get_jobs_dashboard'],
                data: inject_globals(),
                success: function (response) {
                    $('#main_dashboard').html(response);
                    setup_jobs_datatable(nunjucks_urls, site_map);
                },
                error: function (rs, e) {
                    $('#main_dashboard').html(`<strong>` + JSON.stringify(rs) + `</strong>`);
                }
            });
        }
    });
}

function on_click_workers_dashboard(nunjucks_urls, site_map){
    $('#workers_link').on('click', function () {
        $.ajax({
            type: "GET",
            url: site_map['rqmonitor.get_workers_dashboard'],
            data: inject_globals(),
            success: function (response) {
                $('#main_dashboard').html(response);
                setup_worker_datatable(nunjucks_urls, site_map);
            },
            error: function (rs, e) {
                $('#main_dashboard').html(`<strong>` + JSON.stringify(rs) + `</strong>`);
            }
        });
    });
}

function on_click_queues_dashboard(nunjucks_urls, site_map){
    $('#queues_link').on('click', function () {
        $.ajax({
            type: "GET",
            url: site_map['rqmonitor.get_queues_dashboard'],
            data: inject_globals(),
            success: function (response) {
                $('#main_dashboard').html(response);
                setup_queues_datatable(nunjucks_urls, site_map);
            },
            error: function (rs, e) {
                $('#main_dashboard').html(`<strong>` + JSON.stringify(rs) + `</strong>`);
            }
        });
    });
}              
