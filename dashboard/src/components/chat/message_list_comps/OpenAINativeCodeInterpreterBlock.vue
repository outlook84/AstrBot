<template>
    <div class="native-code-block" :class="{ compact: !showHeader }">
        <div v-if="displayExpanded" class="py-3 animate-fade-in">
            <div v-if="statusLabel" class="status-chip" :class="{ 'dark-theme': isDark }">
                {{ tm('nativeCodeInterpreter.status') }}: {{ statusLabel }}
            </div>

            <div class="code-section">
                <div v-if="shikiReady && code" class="code-highlighted" v-html="highlightedCode"></div>
                <pre v-else class="code-fallback" :class="{ 'dark-theme': isDark }">{{ code || 'No code available' }}</pre>
            </div>

            <div v-if="logs" class="result-section">
                <div class="result-label">
                    {{ tm('nativeCodeInterpreter.logs') }}:
                </div>
                <pre class="result-content" :class="{ 'dark-theme': isDark }">{{ logs }}</pre>
            </div>

            <div v-if="images.length" class="image-section">
                <div class="result-label">
                    {{ tm('nativeCodeInterpreter.images') }}:
                </div>
                <div class="image-grid">
                    <img
                        v-for="image in images"
                        :key="image"
                        :src="image"
                        class="result-image"
                        @click="emitOpenImage(image)"
                    />
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { createHighlighter } from 'shiki';
import { useModuleI18n } from '@/i18n/composables';

const props = defineProps({
    toolCall: {
        type: Object,
        required: true
    },
    isDark: {
        type: Boolean,
        default: false
    },
    initialExpanded: {
        type: Boolean,
        default: true
    },
    showHeader: {
        type: Boolean,
        default: true
    },
    forceExpanded: {
        type: Boolean,
        default: null
    }
});

const emit = defineEmits(['open-image-preview']);
const { tm } = useModuleI18n('features/chat');
const isExpanded = ref(props.initialExpanded);
const shikiHighlighter = ref(null);
const shikiReady = ref(false);

const parsedResult = computed(() => {
    if (!props.toolCall.result) return {};
    if (typeof props.toolCall.result === 'object') return props.toolCall.result;
    try {
        return JSON.parse(props.toolCall.result);
    } catch {
        return {};
    }
});

const code = computed(() => {
    try {
        return props.toolCall.args?.code || '';
    } catch {
        return '';
    }
});

const logs = computed(() => {
    const value = parsedResult.value?.logs;
    if (Array.isArray(value)) {
        return value.join('');
    }
    if (typeof value === 'string') {
        return value;
    }
    return '';
});

const images = computed(() => {
    const value = parsedResult.value?.images;
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter((item) => typeof item === 'string' && item);
});

const statusLabel = computed(() => {
    const value = parsedResult.value?.status;
    return typeof value === 'string' ? value : '';
});

const highlightedCode = computed(() => {
    if (!shikiReady.value || !shikiHighlighter.value || !code.value) {
        return '';
    }
    try {
        return shikiHighlighter.value.codeToHtml(code.value, {
            lang: 'python',
            theme: props.isDark ? 'min-dark' : 'github-light'
        });
    } catch (err) {
        console.error('Failed to highlight native code interpreter code:', err);
        return `<pre><code>${code.value}</code></pre>`;
    }
});

const displayExpanded = computed(() => {
    if (props.forceExpanded === null) {
        return isExpanded.value;
    }
    return props.forceExpanded;
});

const emitOpenImage = (url) => {
    emit('open-image-preview', url);
};

onMounted(async () => {
    try {
        shikiHighlighter.value = await createHighlighter({
            themes: ['min-dark', 'github-light'],
            langs: ['python']
        });
        shikiReady.value = true;
    } catch (err) {
        console.error('Failed to initialize Shiki for native code interpreter:', err);
    }
});
</script>

<style scoped>
.native-code-block {
    margin-bottom: 12px;
    margin-top: 6px;
}

.native-code-block.compact {
    margin: 0;
}

.py-3 {
    padding-top: 12px;
    padding-bottom: 12px;
}

.status-chip {
    display: inline-flex;
    margin-bottom: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(21, 101, 192, 0.08);
    color: #1565c0;
    font-size: 12px;
    font-weight: 600;
}

.status-chip.dark-theme {
    background: rgba(144, 202, 249, 0.12);
    color: #90caf9;
}

.code-section {
    margin-bottom: 12px;
}

.code-highlighted {
    border-radius: 6px;
    overflow: hidden;
    font-size: 14px;
    line-height: 1.5;
    overflow-x: auto;
}

.code-fallback {
    margin: 0;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 13px;
    line-height: 1.5;
    background-color: #f5f5f5;
}

.code-fallback.dark-theme {
    background-color: transparent;
}

.result-section,
.image-section {
    margin-top: 12px;
}

.result-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--v-theme-secondaryText);
    margin-bottom: 6px;
    opacity: 0.8;
}

.result-content {
    margin: 0;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 13px;
    line-height: 1.5;
    background-color: #f5f5f5;
    max-height: 300px;
    overflow-y: auto;
}

.result-content.dark-theme {
    background-color: transparent;
}

.image-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 10px;
}

.result-image {
    width: 100%;
    border-radius: 8px;
    cursor: pointer;
    border: 1px solid rgba(0, 0, 0, 0.08);
}

.animate-fade-in {
    animation: fadeIn 0.2s ease-in-out;
}

:deep(.code-highlighted pre) {
    background-color: transparent !important;
}

@keyframes fadeIn {
    from {
        opacity: 0;
    }

    to {
        opacity: 1;
    }
}
</style>
