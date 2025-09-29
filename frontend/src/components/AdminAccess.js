import React, { useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : 'http://localhost:8000/api';

const AdminAccess = ({ onAccess }) => {
  const [showLogin, setShowLogin] = useState(false);
  const [credentials, setCredentials] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API}/auth/login`, {
        email: credentials.email,
        password: credentials.password
      });

      if (response.data.token && response.data.user?.is_admin) {
        localStorage.setItem('token', response.data.token);
        onAccess();
        setShowLogin(false);
      } else {
        setError('No tienes privilegios de administrador');
      }
    } catch (error) {
      setError('Credenciales incorrectas. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    setCredentials({
      ...credentials,
      [e.target.name]: e.target.value
    });
  };

  if (showLogin) {
    return (
      <div className="admin-login-overlay">
        <div className="admin-login-modal">
          <h3>🔐 Acceso de Administrador</h3>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Email:</label>
              <input
                type="email"
                name="email"
                value={credentials.email}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Contraseña:</label>
              <input
                type="password"
                name="password"
                value={credentials.password}
                onChange={handleInputChange}
                required
              />
            </div>
            {error && <div className="error-message">{error}</div>}
            <div className="admin-login-actions">
              <button type="button" onClick={() => setShowLogin(false)}>
                Cancelar
              </button>
              <button type="submit" disabled={loading}>
                {loading ? 'Iniciando...' : 'Acceder'}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-access-card">
      <div className="admin-access-content">
        <h3>⚙️ Panel de Administración</h3>
        <p>Gestiona productos, usuarios y configuraciones del sistema</p>
        <button 
          onClick={() => setShowLogin(true)}
          className="admin-login-btn"
        >
          Iniciar Sesión como Admin
        </button>
        {/* Se eliminan credenciales visibles */}
      </div>
    </div>
  );
};

export default AdminAccess;
