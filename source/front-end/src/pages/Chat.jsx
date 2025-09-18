import { useEffect, useRef, useState } from "react";
import api from "../api";
import { clearToken } from "../auth";

export default function Chat() {
  const [chatId, setChatId] = useState(localStorage.getItem("chat_id") || "");
  const [messages, setMessages] = useState([]);
  const [chats, setChats] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [user, setUser] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [websocket, setWebsocket] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [typing, setTyping] = useState({ isTyping: false, sender: null });
  const [useWebSocket, setUseWebSocket] = useState(true); // Toggle WebSocket on/off

  const listRef = useRef(null);
  const wsRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    // Initial app load
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        setUser(data);
      } catch (e) {
        console.error("Failed to fetch user:", e);
      }

      try {
        const { data } = await api.post("/chat/start", {});
        setChats(data.chats || []);
      } catch (e) {
        console.error("Failed to fetch chats:", e);
      }

      // Restore the last session from localStorage
      const lastChatId = localStorage.getItem("chat_id");
      if (lastChatId && lastChatId !== "undefined" && lastChatId !== "null") {
        console.log("Restoring previous chat session:", lastChatId);
        await loadChat(lastChatId);
      }
    })();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages.length]);

  // WebSocket connection effect
  useEffect(() => {
    if (chatId && useWebSocket) {
      connectWebSocket(chatId);
    } else {
      disconnectWebSocket();
    }

    return () => disconnectWebSocket();
  }, [chatId, useWebSocket]);

  function connectWebSocket(currentChatId) {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      const token = localStorage.getItem("token");

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/api/chat/ws/${currentChatId}${token ? `?token=${token}` : ''}`;

      console.log("Connecting to WebSocket:", wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected");
        setConnectionStatus("connected");
        setWebsocket(ws);

        // Authenticate if needed
        if (token) {
          ws.send(JSON.stringify({
            type: "auth",
            token: token
          }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setConnectionStatus("error");
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setConnectionStatus("disconnected");
        setWebsocket(null);
        wsRef.current = null;

        // Auto-reconnect after 3 seconds
        if (currentChatId && useWebSocket) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log("Attempting to reconnect WebSocket...");
            connectWebSocket(currentChatId);
          }, 3000);
        }
      };

    } catch (error) {
      console.error("Failed to create WebSocket connection:", error);
      setConnectionStatus("error");
    }
  }

  function disconnectWebSocket() {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setWebsocket(null);
    setConnectionStatus("disconnected");
  }

  function handleWebSocketMessage(data) {
    console.log("WebSocket message received:", data);

    switch (data.type) {
      case "new_message":
        setMessages(prev => {
          // Check if message already exists to prevent duplicates
          const exists = prev.some(m => m.id === data.message.id);
          if (exists) return prev;

          return [...prev, {
            ...data.message,
            created_at: data.message.created_at
          }];
        });
        scrollToBottom();
        break;

      case "message_sent":
        // Update temp message with server ID
        setMessages(prev => {
          const updated = [...prev];
          const tempIndex = updated.findIndex(m => m.id?.startsWith('temp_'));
          if (tempIndex !== -1) {
            updated[tempIndex] = {
              ...data.message,
              created_at: data.message.created_at
            };
          }
          return updated;
        });
        break;

      case "typing":
        if (data.sender === "bot") {
          setTyping({
            isTyping: data.is_typing,
            sender: data.sender
          });

          if (data.is_typing) {
            // Clear typing after 10 seconds max
            if (typingTimeoutRef.current) {
              clearTimeout(typingTimeoutRef.current);
            }
            typingTimeoutRef.current = setTimeout(() => {
              setTyping({ isTyping: false, sender: null });
            }, 10000);
          }
        }
        break;

      case "doctor_report_processing":
        setMessages(prev => [...prev, {
          id: `system_${Date.now()}`,
          sender: "system",
          content: data.message,
          created_at: new Date().toISOString()
        }]);
        break;

      case "doctor_report_ready":
        setMessages(prev => [...prev, {
          id: `system_${Date.now()}`,
          sender: "system",
          content: data.message,
          created_at: new Date().toISOString()
        }]);

        if (data.action === "reload_chat") {
          setTimeout(() => loadChat(chatId), 1000);
        }
        break;

      case "error":
        console.error("WebSocket error:", data.message);
        alert(`Error: ${data.message}`);
        break;

      case "pong":
        // Keep-alive response
        break;

      case "auth_success":
        console.log("WebSocket authentication successful");
        break;

      case "auth_error":
        console.error("WebSocket authentication failed");
        // Fall back to REST mode
        setUseWebSocket(false);
        break;

      default:
        console.log("Unknown WebSocket message type:", data.type);
    }
  }

  function scrollToBottom() {
    setTimeout(() => {
      const el = listRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }, 0);
  }

  async function loadChat(id) {
    try {
      const { data } = await api.get(`/chat/${id}`);
      setChatId(id);
      localStorage.setItem("chat_id", id);
      setMessages(data.messages || []);
    } catch (e) {
      console.error("Failed to load chat:", e);
    }
  }

  async function send() {
    if (!input.trim() || sending) return;

    const text = input.trim();
    setInput("");

    // Generate temp message ID
    const tempId = `temp_${Date.now()}`;
    const userMsg = {
      id: tempId,
      sender: "user",
      content: text,
      created_at: new Date().toISOString()
    };

    // Add user message to UI immediately
    setMessages((m) => [...m, userMsg]);
    scrollToBottom();

    setSending(true);

    // Try WebSocket first if available
    if (websocket && websocket.readyState === WebSocket.OPEN && chatId) {
      try {
        websocket.send(JSON.stringify({
          type: "send_message",
          content: text
        }));

        // WebSocket handles the response, just clean up
        setSending(false);
        return;

      } catch (wsError) {
        console.warn("WebSocket send failed, falling back to REST:", wsError);
        // Fall through to REST API
      }
    }

    // REST API fallback (existing logic)
    try {
      let currentChatId = chatId;

      if (!currentChatId || currentChatId === "undefined") {
        console.log("Creating new chat with first message using combined endpoint");

        const { data } = await api.post("/chat/start-with-message", {
          content: text
        });

        localStorage.setItem("chat_id", data.chat_id);
        setChatId(data.chat_id);
        setMessages(data.messages || []);

        // Refresh chat list
        try {
          const { data: chatsData } = await api.get("/chat/list");
          setChats(chatsData.chats || []);
        } catch (e) {
          console.warn("Failed to refresh chat list:", e);
        }

      } else {
        console.log("Sending to existing chat:", currentChatId);

        const { data } = await api.post("/chat/send", {
          chat_id: currentChatId,
          content: text
        });

        // Replace temp message with server response
        setMessages((m) => [
          ...m.filter((x) => x.id !== tempId),
          {
            id: data.user_msg_id,
            sender: "user",
            content: text,
            created_at: new Date().toISOString()
          },
          {
            id: data.bot_msg_id,
            sender: "bot",
            content: data.reply,
            created_at: new Date().toISOString()
          },
        ]);

        try {
          const { data: chatsData } = await api.get("/chat/list");
          setChats(chatsData.chats || []);
        } catch (e) {
          console.warn("Failed to refresh chat list:", e);
        }
      }

      scrollToBottom();

    } catch (error) {
      console.error("Failed to send message:", error);

      // Remove the temporary message on error
      setMessages((m) => m.filter((x) => x.id !== tempId));

      // Handle specific errors (existing logic)
      if (error.response?.status === 403 || error.response?.status === 404) {
        console.warn("Chat access error, creating new chat...");
        localStorage.removeItem("chat_id");
        setChatId("");

        try {
          const { data } = await api.post("/chat/start-with-message", {
            content: text
          });

          setChatId(data.chat_id);
          localStorage.setItem("chat_id", data.chat_id);
          setMessages(data.messages || []);

          const { data: chatsData } = await api.get("/chat/list");
          setChats(chatsData.chats || []);

        } catch (retryError) {
          console.error("Failed to create new chat during retry:", retryError);
          alert("Failed to send message. Please try again.");
        }
      } else {
        alert(`Failed to send message: ${error.response?.data?.detail || error.message}`);
      }

    } finally {
      setSending(false);
    }
  }

  // Send typing indicator
  function handleInputChange(e) {
    setInput(e.target.value);

    // Send typing indicator via WebSocket
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: "typing",
        is_typing: e.target.value.length > 0
      }));
    }
  }

  async function newChat() {
    try {
      const { data } = await api.post("/chat/start", {});

      setChatId(data.chat_id);
      setMessages(data.messages || []);
      localStorage.setItem("chat_id", data.chat_id);

      const { data: chatsData } = await api.get("/chat/list");
      setChats(chatsData.chats || []);

      console.log("New chat created:", data.chat_id);
    } catch (error) {
      console.error("Failed to create new chat:", error);
      alert("Failed to create new chat. Please try again.");
    }
  }

  async function clearChat() {
    try {
      await api.delete("/chat/clear");
      localStorage.removeItem("chat_id");
      setChatId("");
      setMessages([]);
      setChats([]);
    } catch (e) {
      console.error("Failed to clear chat:", e);
    }
  }

  // Connection status indicator
  const getStatusColor = () => {
    switch (connectionStatus) {
      case "connected": return "text-green-400";
      case "connecting": return "text-yellow-400";
      case "error": return "text-red-400";
      default: return "text-gray-400";
    }
  };

  const getStatusText = () => {
    switch (connectionStatus) {
      case "connected": return useWebSocket ? "Real-time" : "REST Mode";
      case "connecting": return "Connecting...";
      case "error": return "Connection Error";
      default: return useWebSocket ? "Connecting..." : "REST Mode";
    }
  };

  return (
    <div className="fixed inset-0 flex bg-gray-900 text-gray-100">
      {/* Sidebar */}
      <aside
        className={`transition-all duration-300 bg-gray-800 border-r border-white/10 flex flex-col
          ${sidebarOpen ? "w-64" : "w-0 overflow-hidden"}`}
      >
        <div className="p-4 font-semibold border-b border-white/10 flex justify-between items-center">
          <span>Conversations</span>
          <button
            onClick={() => setSidebarOpen(false)}
            className="text-xs text-gray-400 hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {chats.length === 0 && (
            <div className="text-sm text-gray-400 p-4">No history yet</div>
          )}
          {chats.map((c) => (
            <button
              key={c.chat_id}
              onClick={() => loadChat(c.chat_id)}
              className={`w-full text-left px-4 py-2 hover:bg-gray-700 ${
                chatId === c.chat_id ? "bg-gray-700 font-bold" : ""
              }`}
            >
              {c.topic || `Chat ${c.chat_id.slice(0, 6)}`}
            </button>
          ))}
        </div>
        <div className="p-4 space-y-2 border-t border-white/10">
          {/* WebSocket toggle */}
          <label className="flex items-center text-xs text-gray-400">
            <input
              type="checkbox"
              checked={useWebSocket}
              onChange={(e) => setUseWebSocket(e.target.checked)}
              className="mr-2"
            />
            Enable Real-time
          </label>

          <button onClick={newChat} className="w-full px-3 py-1 rounded-lg bg-sky-600 hover:bg-sky-700">New Chat</button>
          <button onClick={clearChat} className="w-full px-3 py-1 rounded-lg bg-gray-700 hover:bg-gray-600">Clear All</button>
          <button
            onClick={() => { clearToken(); window.location.href = "/login"; }}
            className="w-full px-3 py-1 rounded-lg bg-red-600 hover:bg-red-700"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="shrink-0 h-14 border-b border-white/10 flex items-center px-4 justify-between">
          <div className="flex items-center">
            <button
              onClick={() => setSidebarOpen(true)}
              className="px-2 py-1 mr-3 rounded bg-gray-700 hover:bg-gray-600"
            >
              ☰
            </button>
            <div className="font-semibold">
              Nusantara CaRas {user ? `— Welcome, ${user.display_name}` : ""}
            </div>
          </div>

          {/* Connection status */}
          <div className={`text-xs ${getStatusColor()} flex items-center`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${
              connectionStatus === "connected" ? "bg-green-400" :
              connectionStatus === "connecting" ? "bg-yellow-400" :
              connectionStatus === "error" ? "bg-red-400" : "bg-gray-400"
            }`}></span>
            {getStatusText()}
          </div>
        </header>

        {/* Messages */}
        <main className="flex-1 overflow-hidden">
          <div ref={listRef} className="h-full overflow-y-auto max-w-5xl mx-auto px-4 py-6 space-y-3">
            {messages.length === 0 && (
              <div className="text-sm text-gray-400 text-center mt-20">
                Kesehatan anda adalah prioritas kami.
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] px-3 py-2 rounded-xl whitespace-pre-wrap ${
                    m.sender === "user"
                      ? "bg-sky-600 text-white rounded-br-sm"
                      : m.sender === "bot"
                      ? "bg-gray-800 rounded-bl-sm"
                      : m.sender === "system"
                      ? "bg-amber-700/30 text-amber-200 text-center text-sm"
                      : "bg-gray-700"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {typing.isTyping && typing.sender === "bot" && (
              <div className="flex justify-start">
                <div className="bg-gray-800 rounded-xl px-4 py-3 rounded-bl-sm">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Composer */}
        <footer className="shrink-0 border-t border-white/10">
          <div className="max-w-5xl mx-auto p-4 flex gap-2">
            <input
              className="flex-1 px-3 py-3 rounded-xl bg-gray-800 text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="Kirim keluhan anda..."
              value={input}
              onChange={handleInputChange}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              disabled={sending}
            />
            <button
              onClick={send}
              disabled={sending}
              className="px-4 rounded-xl bg-sky-600 hover:bg-sky-700 disabled:opacity-50"
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}