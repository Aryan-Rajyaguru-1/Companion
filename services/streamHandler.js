// services/streamHandler.js
// Handle streaming responses from the API

class StreamHandler {
  constructor() {
    this.activeStreams = new Map();
  }

  startStream(conversationId, onChunk, onComplete, onError) {
    // Placeholder for streaming implementation
    // Would use SSE or WebSocket
    const streamId = `stream_${conversationId}_${Date.now()}`;
    this.activeStreams.set(streamId, { onChunk, onComplete, onError });
    return streamId;
  }

  stopStream(streamId) {
    this.activeStreams.delete(streamId);
  }

  // Simulate streaming for now
  async simulateStream(message, onChunk) {
    const words = message.split(' ');
    for (const word of words) {
      await new Promise(resolve => setTimeout(resolve, 100));
      onChunk(word + ' ');
    }
  }
}

export default new StreamHandler();