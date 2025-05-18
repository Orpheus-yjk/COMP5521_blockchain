"""
区块链Web服务后端
功能：
- 提供节点管理REST API
- WebSocket实时通信
- Kubernetes集成
"""

from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from kubernetes import client, config
import logging

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化Kubernetes客户端
try:
    config.load_kube_config()
    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()
except Exception as e:
    logging.error(f"Kubernetes初始化失败: {str(e)}")


@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """获取所有节点信息"""
    try:
        nodes = []
        pods = core_api.list_namespaced_pod(namespace="default", label_selector="app=blockchain")

        for pod in pods.items:
            node_type = pod.metadata.annotations.get('nodeType', 'Unknown')
            nodes.append({
                "id": pod.metadata.name,
                "type": node_type,
                "ip": pod.status.pod_ip,
                "status": pod.status.phase,
                "address": f"{pod.status.pod_ip}:5000",
                "neighbors": []  # 需要从网络模块获取
            })
        return jsonify(nodes)
    except Exception as e:
        logging.error(f"获取节点失败: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    """删除指定节点"""
    try:
        # 删除Pod
        core_api.delete_namespaced_pod(
            name=node_id,
            namespace="default",
            body=client.V1DeleteOptions()
        )

        # 删除关联Service
        core_api.delete_namespaced_service(
            name=f"svc-{node_id}",
            namespace="default"
        )

        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"删除节点失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/nodes/<node_id>/peers', methods=['POST'])
def manage_peer(node_id):
    """管理节点邻居"""
    data = request.json
    action = data.get('action')
    target = data.get('target')

    if action == 'remove':
        # 这里需要调用网络模块的remove_neighbor方法
        # success = network.remove_neighbor(target, bidirectional=True)
        success = True  # 模拟成功
        return jsonify({"success": success})
    else:
        return jsonify({"error": "无效操作"}), 400


@socketio.on('node_click')
def handle_node_click(node_id):
    """处理节点点击事件"""
    try:
        pod = core_api.read_namespaced_pod(node_id, namespace="default")
        details = {
            "id": pod.metadata.name,
            "type": pod.metadata.annotations.get('nodeType', 'Unknown'),
            "status": pod.status.phase,
            "ip": pod.status.pod_ip,
            "creation_time": pod.metadata.creation_timestamp
        }
        socketio.emit('node_details', details)
    except Exception as e:
        logging.error(f"获取节点详情失败: {str(e)}")


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
