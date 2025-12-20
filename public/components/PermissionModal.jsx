// components/PermissionModal.jsx
// Handle permission requests for sensitive operations

import React, { useState, useEffect } from 'react';

const PermissionModal = () => {
  const [showModal, setShowModal] = useState(false);
  const [permissionRequest, setPermissionRequest] = useState(null);

  // Listen for permission requests from global events
  useEffect(() => {
    const handlePermissionRequest = (event) => {
      setPermissionRequest(event.detail);
      setShowModal(true);
    };

    window.addEventListener('permission-request', handlePermissionRequest);
    return () => window.removeEventListener('permission-request', handlePermissionRequest);
  }, []);

  const handlePermission = (granted) => {
    if (permissionRequest?.callback) {
      permissionRequest.callback(granted);
    }

    // Dispatch permission response event
    window.dispatchEvent(new CustomEvent('permission-response', {
      detail: { granted, request: permissionRequest }
    }));

    setShowModal(false);
    setPermissionRequest(null);
  };

  const getPermissionIcon = (type) => {
    const icons = {
      file_access: '📁',
      network_access: '🌐',
      code_execution: '⚙️',
      data_access: '💾',
      default: '🔒'
    };
    return icons[type] || icons.default;
  };

  const getPermissionLevel = (type) => {
    const levels = {
      file_access: 'Medium',
      network_access: 'High',
      code_execution: 'High',
      data_access: 'Medium',
      default: 'Low'
    };
    return levels[type] || levels.default;
  };

  if (!showModal || !permissionRequest) return null;

  const level = getPermissionLevel(permissionRequest.type);
  const levelClass = level.toLowerCase();

  return (
    <div className="permission-modal-overlay">
      <div className="permission-modal">
        <div className="permission-header">
          <div className="permission-icon">
            {getPermissionIcon(permissionRequest.type)}
          </div>
          <h3>Permission Required</h3>
          <span className={`permission-level ${levelClass}`}>
            {level} Risk
          </span>
        </div>

        <div className="permission-content">
          <p className="permission-message">
            {permissionRequest.message || 'This action requires special permission.'}
          </p>

          {permissionRequest.details && (
            <div className="permission-details">
              <h4>Details:</h4>
              <ul>
                {permissionRequest.details.map((detail, index) => (
                  <li key={index}>{detail}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="permission-warning">
            <strong>⚠️ Security Notice:</strong> Only grant permissions to actions you trust.
            This permission will be remembered for this session.
          </div>
        </div>

        <div className="permission-actions">
          <button
            className="permission-deny"
            onClick={() => handlePermission(false)}
          >
            Deny
          </button>
          <button
            className="permission-allow"
            onClick={() => handlePermission(true)}
            autoFocus
          >
            Allow
          </button>
        </div>
      </div>
    </div>
  );
};

export default PermissionModal;