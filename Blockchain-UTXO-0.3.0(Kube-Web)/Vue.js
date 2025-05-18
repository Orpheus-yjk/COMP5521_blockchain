// 前端伪代码 (Vue.js)
methods: {
    async deletePeer(sourceNodeId, targetNodeId) {
      const res = await axios.post(`/api/nodes/${sourceNodeId}/peers`, {
        action: 'remove',
        target: targetNodeId
      });
      if (res.data.success) {
        this.$toast("邻居删除成功");
        this.refreshTopology();
      }
    },
  
    async deleteNode(nodeId) {
      if (confirm("确定删除节点？此操作不可逆！")) {
        const res = await axios.delete(`/api/nodes/${nodeId}`);
        if (res.data.success) {
          this.$toast("节点已删除");
          this.nodes = this.nodes.filter(n => n.id !== nodeId);
        }
      }
    }
  }