<template>
  <div class="qr-code-viewer">
    <img
      v-if="imageSrc"
      :src="imageSrc"
      :alt="alt"
      class="qr-code-image"
    />
    <div v-else class="qr-code-empty">
      {{ emptyHint }}
    </div>
  </div>
</template>

<script>
export default {
  name: "QrCodeViewer",
  props: {
    value: {
      type: String,
      default: "",
    },
    alt: {
      type: String,
      default: "QR Code",
    },
    emptyHint: {
      type: String,
      default: "No QR code available",
    },
  },
  computed: {
    imageSrc() {
      const value = String(this.value || "").trim();
      if (!value) {
        return "";
      }
      if (
        value.startsWith("http://")
        || value.startsWith("https://")
        || value.startsWith("data:image/")
      ) {
        return value;
      }
      return "";
    },
  },
};
</script>

<style scoped>
.qr-code-viewer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.qr-code-image {
  display: block;
  width: 180px;
  max-width: 100%;
  border-radius: 8px;
}

.qr-code-empty {
  color: rgba(0, 0, 0, 0.6);
  font-size: 12px;
}
</style>
