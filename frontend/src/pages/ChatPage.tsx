import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import ChatArea from "../components/ChatArea";

export default function ChatPage() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const [key, setKey] = useState(0);

  const handleChatCreated = useCallback(
    (newChatId: string) => {
      setKey((k) => k + 1);
    },
    []
  );

  return (
    <Layout>
      <ChatArea
        key={chatId || key}
        chatId={chatId || null}
        onChatCreated={handleChatCreated}
      />
    </Layout>
  );
}
