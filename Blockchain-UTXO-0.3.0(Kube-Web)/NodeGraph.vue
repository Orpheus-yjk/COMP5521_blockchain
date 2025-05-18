// src/components/NodeGraph.vue
export default {
  methods: {
    async manualSync(nodeId) {
      const res = await axios.post(`/api/nodes/${nodeId}/sync`);
      if (res.data.success) {
        this.$toast("同步成功");
      } else {
        this.$toast.error("同步失败");
      }
    },
    copyPrivateKey(nodeId) {
      navigator.clipboard.writeText(this.nodes[nodeId].privateKey)
        .then(() => this.$toast("私钥已复制"))
        .catch(() => this.$toast.error("复制失败"));
    }
  }
}