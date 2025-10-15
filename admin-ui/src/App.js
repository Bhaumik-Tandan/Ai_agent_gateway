import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8080';

function App() {
  const [activeTab, setActiveTab] = useState('decisions');
  const [agents, setAgents] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
    // Auto-refresh every 5 seconds
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'agents') {
        const res = await axios.get(`${API_BASE}/api/admin/agents`);
        setAgents(res.data.agents || []);
      } else if (activeTab === 'policies') {
        const res = await axios.get(`${API_BASE}/api/admin/policies`);
        setPolicies(res.data.policies || []);
      } else if (activeTab === 'decisions') {
        const res = await axios.get(`${API_BASE}/api/admin/decisions`);
        setDecisions(res.data.decisions || []);
      } else if (activeTab === 'approvals') {
        const res = await axios.get(`${API_BASE}/api/admin/approvals/pending`);
        setApprovals(res.data.pending_approvals || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (approvalId) => {
    try {
      await axios.post(`${API_BASE}/api/approve/${approvalId}`, {}, {
        headers: {
          'X-Agent-ID': 'admin-ui'
        }
      });
      alert('Request approved and executed!');
      loadData();
    } catch (err) {
      alert(`Error: ${err.response?.data?.detail?.reason || err.message}`);
    }
  };

  return (
    <div className="App">
      <header className="header">
        <h1>🛡️ Aegis Gateway Admin</h1>
        <p>Real-time monitoring and policy management</p>
      </header>

      <nav className="tabs">
        <button 
          className={activeTab === 'decisions' ? 'active' : ''} 
          onClick={() => setActiveTab('decisions')}
        >
          📊 Recent Decisions
        </button>
        <button 
          className={activeTab === 'agents' ? 'active' : ''} 
          onClick={() => setActiveTab('agents')}
        >
          🤖 Agents
        </button>
        <button 
          className={activeTab === 'policies' ? 'active' : ''} 
          onClick={() => setActiveTab('policies')}
        >
          📋 Policies
        </button>
        <button 
          className={activeTab === 'approvals' ? 'active' : ''} 
          onClick={() => setActiveTab('approvals')}
        >
          ✅ Pending Approvals {approvals.length > 0 && `(${approvals.length})`}
        </button>
      </nav>

      <main className="content">
        {loading && <div className="loading">Loading...</div>}
        {error && <div className="error">Error: {error}</div>}

        {!loading && !error && (
          <>
            {activeTab === 'decisions' && <DecisionsView decisions={decisions} />}
            {activeTab === 'agents' && <AgentsView agents={agents} />}
            {activeTab === 'policies' && <PoliciesView policies={policies} />}
            {activeTab === 'approvals' && <ApprovalsView approvals={approvals} onApprove={handleApprove} />}
          </>
        )}
      </main>
    </div>
  );
}

function DecisionsView({ decisions }) {
  return (
    <div className="section">
      <h2>Recent Decisions (Last {decisions.length})</h2>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Agent</th>
              <th>Tool</th>
              <th>Action</th>
              <th>Decision</th>
              <th>Reason</th>
              <th>Parent</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((dec, idx) => (
              <tr key={idx}>
                <td className="timestamp">{new Date(dec.timestamp).toLocaleString()}</td>
                <td className="agent-id">{dec.agent_id}</td>
                <td>{dec.tool}</td>
                <td>{dec.action}</td>
                <td>
                  <span className={`badge ${dec.decision}`}>
                    {dec.decision}
                  </span>
                </td>
                <td className="reason">{dec.reason}</td>
                <td>{dec.parent_agent || '-'}</td>
              </tr>
            ))}
            {decisions.length === 0 && (
              <tr>
                <td colSpan="7" style={{textAlign: 'center', padding: '2rem'}}>
                  No decisions yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AgentsView({ agents }) {
  return (
    <div className="section">
      <h2>Configured Agents ({agents.length})</h2>
      <div className="cards">
        {agents.map((agent, idx) => (
          <div key={idx} className="card">
            <h3>🤖 {agent.id}</h3>
            <div className="card-section">
              <h4>Permissions</h4>
              {agent.permissions.map((perm, pidx) => (
                <div key={pidx} className="permission">
                  <strong>{perm.tool}</strong>
                  <div className="actions">{perm.actions.join(', ')}</div>
                  {perm.conditions && (
                    <div className="conditions">
                      Conditions: {JSON.stringify(perm.conditions)}
                    </div>
                  )}
                  {perm.require_approval && (
                    <span className="badge approval-required">Requires Approval</span>
                  )}
                </div>
              ))}
            </div>
            {agent.allow_only_parents && (
              <div className="card-section">
                <h4>Parent Restrictions</h4>
                <div className="parent-rule">
                  Only callable by: {agent.allow_only_parents.join(', ')}
                </div>
              </div>
            )}
            {agent.deny_if_parent && (
              <div className="card-section">
                <h4>Parent Denials</h4>
                <div className="parent-rule deny">
                  Denied if parent: {agent.deny_if_parent.join(', ')}
                </div>
              </div>
            )}
          </div>
        ))}
        {agents.length === 0 && (
          <div className="empty">No agents configured</div>
        )}
      </div>
    </div>
  );
}

function PoliciesView({ policies }) {
  return (
    <div className="section">
      <h2>Policy Files ({policies.length})</h2>
      <div className="cards">
        {policies.map((policy, idx) => (
          <div key={idx} className="card">
            <h3>📋 {policy.path.split('/').pop()}</h3>
            <div className="policy-info">
              <div>
                <strong>Version:</strong> {policy.version}
              </div>
              <div>
                <strong>Agents:</strong> {policy.agent_count}
              </div>
              <div>
                <strong>Path:</strong> <code>{policy.path}</code>
              </div>
            </div>
          </div>
        ))}
        {policies.length === 0 && (
          <div className="empty">No policies loaded</div>
        )}
      </div>
    </div>
  );
}

function ApprovalsView({ approvals, onApprove }) {
  return (
    <div className="section">
      <h2>Pending Approvals ({approvals.length})</h2>
      <div className="cards">
        {approvals.map((approval, idx) => (
          <div key={idx} className="card approval-card">
            <div className="approval-header">
              <h3>🔐 Approval Request</h3>
              <span className="badge pending">{approval.status}</span>
            </div>
            <div className="approval-details">
              <div><strong>Agent:</strong> {approval.agent_id}</div>
              <div><strong>Tool:</strong> {approval.tool}</div>
              <div><strong>Action:</strong> {approval.action}</div>
              <div><strong>Requested:</strong> {new Date(approval.created_at).toLocaleString()}</div>
              {approval.parent_agent && (
                <div><strong>Parent Agent:</strong> {approval.parent_agent}</div>
              )}
              <div className="params">
                <strong>Parameters:</strong>
                <pre>{JSON.stringify(approval.params, null, 2)}</pre>
              </div>
            </div>
            <button 
              className="approve-button"
              onClick={() => onApprove(approval.id)}
            >
              ✅ Approve & Execute
            </button>
          </div>
        ))}
        {approvals.length === 0 && (
          <div className="empty">No pending approvals</div>
        )}
      </div>
    </div>
  );
}

export default App;

