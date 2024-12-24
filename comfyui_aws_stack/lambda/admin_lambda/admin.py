import boto3
import os


def handler(event, context):
    asg_name = os.environ.get("ASG_NAME")
    ecs_cluster_name = os.environ.get("ECS_CLUSTER_NAME")
    ecs_service_name = os.environ.get("ECS_SERVICE_NAME")

    # Clients
    asg_client = boto3.client('autoscaling')
    ecs_client = boto3.client('ecs')

    try:
        # Get ASG and ECS status
        asg_response = asg_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name])
        ecs_response = ecs_client.describe_services(
            cluster=ecs_cluster_name, services=[ecs_service_name])

        desired_capacity = asg_response['AutoScalingGroups'][0]['DesiredCapacity']
        running_tasks_count = ecs_response['services'][0]['runningCount']
        instances = asg_response['AutoScalingGroups'][0]['Instances']

        # Determine the status and what to display
        if desired_capacity > 0 and running_tasks_count > 0 and instances:
            # ComfyUI is up and running
            display_restart_shutdown = True
            display_scaleup = False
            status_message = ""
        elif desired_capacity > 0 and instances:
            # ComfyUI is currently scaling up
            display_restart_shutdown = False
            display_scaleup = False
            status_message = "ComfyUI is currently scaling up. It may take 5-10 minutes"
        elif desired_capacity == 0 and running_tasks_count > 0:
            # ComfyUI is currently scaling down
            display_restart_shutdown = False
            display_scaleup = False
            status_message = "ComfyUI is currently scaling down."
        elif desired_capacity == 0 and running_tasks_count == 0:
            # ComfyUI is currently scaling down
            display_restart_shutdown = False
            display_scaleup = True
            status_message = ""
        else:
            display_restart_shutdown = False
            display_scaleup = False
            status_message = "ComfyUI is in an unexpected state."

        # HTML Content
        restart_shutdown_html = """
        <div style='display: flex; justify-content: space-around; gap: 25px;'>
            <div>
                <a href='/admin/restart' class='button-link'>Restart Docker</a>
            </div>
            <div>
                <a href='/admin/shutdown' class='button-link'>Shutdown ComfyUI</a>
            </div>
        </div>
        """ if display_restart_shutdown else ""

        scaleup_html = """
        <div>
            <p>Scale Up ComfyUI</p>
            <a href='/admin/scaleup' class='button-link'>Scale Up</a>
        </div>
        """ if display_scaleup else ""

        status_html = f"<p id='status-message'>{status_message}</p>" if status_message else ""
        if "ComfyUI is currently scaling up." in status_html:
            status_html += '<div class="loader"></div>'

        # Full HTML Content
        html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="X-UA-Compatible" content="ie=edge">
                <title>ComfyUI Admin Page</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background-color: #202020;
                        margin: 0;
                        padding: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        color: #333;
                    }}
                    main {{
                        text-align: center;
                        background-color: #ffffff;
                        padding: 40px;
                        border-radius: 5px;
                        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                        max-width: 600px;
                    }}
                    .button-link {{
                        display: inline-block;
                        background-color: #54646f;
                        color: white;
                        padding: 10px 20px;
                        text-decoration: none;
                        border-radius: 2px;
                        transition: background-color 0.3s ease;
                    }}
                    .button-link:hover {{
                        background-color: #005fa3;
                    }}
                    .loader {{
                        border: 5px solid #f3f3f3;
                        border-top: 5px solid #3498db;
                        border-radius: 50%;
                        width: 50px;
                        height: 50px;
                        animation: spin 1s linear infinite;
                        margin: 20px auto;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
                <script>
                    function checkAndReload() {{
                        const statusMessage = document.getElementById('status-message');
                        if (statusMessage && statusMessage.textContent.includes("ComfyUI is currently scaling up.")) {{
                            setTimeout(() => {{
                                location.reload();
                            }}, 30000); // reload every 30 seconds
                        }}
                    }}
                    window.onload = checkAndReload;
                </script>
            </head>
            <body>
                <main>
                    <h1>ComfyUI Admin</h1>
                    {restart_shutdown_html}
                    {scaleup_html}
                    {status_html}
                </main>
            </body>
            </html>
            """
    except Exception as e:
        # Handle any exceptions that occur
        print(f"Error: {e}")
        html = "<p>Error occurred. Unable to determine the status of ComfyUI.</p>"

    return {"statusCode": 200, "body": html, "headers": {"Content-Type": "text/html"}}
