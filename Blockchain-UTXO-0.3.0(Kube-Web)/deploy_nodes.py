"""
Kubernetes区块链节点部署模块
功能：
- 部署指定数量的区块链节点（Full和SPV类型）
- 自动配置Service和PVC
- 支持节点类型动态分配
"""

from kubernetes import client, config


def deploy_cluster(n_nodes: int):
    """部署区块链节点集群"""
    try:
        config.load_kube_config()
        apps_api = client.AppsV1Api()
        core_api = client.CoreV1Api()

        # 计算节点类型分布
        spv_count = max(1, n_nodes // 7)  # 至少1个SPV节点
        full_count = n_nodes - spv_count

        # 创建SPV节点部署
        spv_deployment = create_deployment(spv_count, "SPV")
        apps_api.create_namespaced_deployment(namespace="default", body=spv_deployment)

        # 创建Full节点部署
        if full_count > 0:
            full_deployment = create_deployment(full_count, "Full")
            apps_api.create_namespaced_deployment(namespace="default", body=full_deployment)

        # 为每个节点创建Service
        for i in range(n_nodes):
            create_node_service(f"blockchain-node-{i}", core_api)

        print(f"成功部署区块链集群: {spv_count}个SPV节点, {full_count}个Full节点")

    except Exception as e:
        print(f"部署失败: {str(e)}")
        raise


def create_deployment(replicas: int, node_type: str) -> dict:
    """创建节点Deployment配置"""
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"blockchain-{node_type.lower()}-node",
            "labels": {"app": "blockchain", "type": node_type}
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": "blockchain", "type": node_type}},
            "template": {
                "metadata": {
                    "labels": {"app": "blockchain", "type": node_type},
                    "annotations": {"nodeType": node_type}
                },
                "spec": {
                    "containers": [{
                        "name": "node",
                        "image": "blockchain-node:0.3.0",
                        "ports": [
                            {"containerPort": 5000, "name": "p2p"},
                            {"containerPort": 5001, "name": "api"}
                        ],
                        "env": [
                            {"name": "NODE_TYPE", "value": node_type},
                            {"name": "P2P_PORT", "value": "5000"},
                            {"name": "API_PORT", "value": "5001"}
                        ],
                        "volumeMounts": [{
                            "name": "blockchain-data",
                            "mountPath": "/data"
                        }]
                    }],
                    "volumes": [{
                        "name": "blockchain-data",
                        "persistentVolumeClaim": {
                            "claimName": f"blockchain-{node_type.lower()}-pvc"
                        }
                    }]
                }
            }
        }
    }


def create_node_service(pod_name: str, core_api: client.CoreV1Api):
    """为节点创建Service"""
    service = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=f"svc-{pod_name}",
            labels={"app": "blockchain"}
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "blockchain"},
            ports=[
                client.V1ServicePort(name="p2p", port=5000, target_port=5000),
                client.V1ServicePort(name="api", port=5001, target_port=5001)
            ]
        )
    )
    core_api.create_namespaced_service(namespace="default", body=service)


def delete_node(node_id: str) -> bool:
    """
    删除Kubernetes中的区块链节点
    Args:
        node_id: 节点ID或Pod名称
    Returns:
        bool: 是否成功删除
    """
    from kubernetes import client as k8s_client, config
    from kubernetes.client.exceptions import ApiException
    try:

        # 加载Kubernetes配置
        config.load_kube_config()
        core_api = k8s_client.CoreV1Api()

        # 获取Pod详情
        pod_name = f"blockchain-node-{node_id}" if node_id.isdigit() else node_id
        pod = core_api.read_namespaced_pod(
            name=pod_name,
            namespace="default"
        )

        # 删除关联Service
        try:
            core_api.delete_namespaced_service(
                name=f"svc-{pod.metadata.name}",
                namespace="default"
            )
        except ApiException as e:
            if e.status != 404:  # 忽略Service不存在的错误
                raise

        # 删除PVC（如果存在）
        if pod.spec.volumes:
            for vol in pod.spec.volumes:
                if vol.persistent_volume_claim:
                    try:
                        core_api.delete_namespaced_persistent_volume_claim(
                            name=vol.persistent_volume_claim.claim_name,
                            namespace="default"
                        )
                    except ApiException as e:
                        if e.status != 404:  # 忽略PVC不存在的错误
                            raise

        # 删除Pod
        core_api.delete_namespaced_pod(
            name=pod.metadata.name,
            namespace="default"
        )

        # 更新拓扑。。。。
        return True

    except ApiException as e:
        import logging
        logging.error(f"Kubernetes API错误: {e.reason}")
        return False
    except Exception as e:
        import logging
        logging.error(f"删除节点失败: {str(e)}")
        return False


# 同时需要添加_is_node_active方法
def _is_node_active(ip: str) -> bool:
    """检查节点是否活跃"""
    try:
        import requests
        response = requests.get(f"http://{ip}:5001/api/status", timeout=3)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    node_count = int(input("请输入要部署的节点数量: "))
    deploy_cluster(node_count)
