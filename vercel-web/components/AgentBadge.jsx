// components/AgentBadge.jsx
// Display agent information

import React from 'react';

const AgentBadge = ({ agent }) => {
  const getAgentInfo = (agent) => {
    const agents = {
      brain_agent: { name: 'Brain Agent', icon: '🧠', description: 'Main reasoning engine' },
      file_agent: { name: 'File Agent', icon: '📁', description: 'File system operations' },
      code_agent: { name: 'Code Agent', icon: '💻', description: 'Code analysis and generation' },
      search_agent: { name: 'Search Agent', icon: '🔍', description: 'Information retrieval' },
    };
    return agents[agent] || { name: 'Unknown Agent', icon: '❓', description: 'Unknown functionality' };
  };

  const info = getAgentInfo(agent);

  return (
    <div className="agent-badge" title={info.description}>
      <span className="agent-icon">{info.icon}</span>
      <span className="agent-name">{info.name}</span>
    </div>
  );
};

export default AgentBadge;