import React, { useState, useEffect } from 'react';

const AdminPanel = ({ onBack }) => {
  const [admin, setAdmin] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showLogin, setShowLogin] = useState(!token);
  const [showProductModal, setShowProductModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    price: '',
    category: '',
    stock: '',
    image_url: '',
    requires_prescription: false,
    active: true
  });

  const API_BASE = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : 'http://localhost:8000/api';

  // Estilos en línea
  const styles = {
    adminLoginContainer: {
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center',
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '20px'
    },
    adminLoginForm: {
      background: 'white', 
      padding: '2rem', 
      borderRadius: '12px',
      boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)', 
      width: '100%', 
      maxWidth: '400px'
    },
    formGroup: {
      marginBottom: '1.5rem'
    },
    label: {
      display: 'block', 
      marginBottom: '0.5rem', 
      fontWeight: '600',
      color: '#333'
    },
    input: {
      width: '100%', 
      padding: '0.75rem', 
      border: '2px solid #e5e7eb', 
      borderRadius: '8px',
      fontSize: '1rem'
    },
    submitButton: {
      width: '100%', 
      padding: '0.75rem', 
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white', 
      border: 'none', 
      borderRadius: '8px', 
      fontSize: '1rem',
      fontWeight: '600',
      cursor: 'pointer'
    },
    backButton: {
      width: '100%', 
      marginTop: '1rem', 
      padding: '0.75rem',
      background: '#6b7280', 
      color: 'white', 
      border: 'none', 
      borderRadius: '8px', 
      cursor: 'pointer'
    }
  };

  useEffect(() => {
    if (token) {
      verifyToken();
    }
  }, [token]);

  useEffect(() => {
    if (admin) {
      loadProducts();
    }
  }, [admin]);

const verifyToken = async () => {
  try {
    const response = await fetch(`${API_BASE}/auth/me`, {
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const userData = await response.json();
      // Verificar si es admin
      if (userData.is_admin) {
        setAdmin(userData);
        setShowLogin(false);
      } else {
        throw new Error('No admin privileges');
      }
    } else {
      throw new Error('Invalid token');
    }
  } catch (error) {
    console.error('Token verification failed:', error);
    localStorage.removeItem('token');
    setToken(null);
    setShowLogin(true);
  }
};

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData(e.target);
    const email = formData.get('email');
    const password = formData.get('password');

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (response.ok) {
        const data = await response.json();
        // Debe venir user con is_admin=true
        if (!data.user?.is_admin) {
          alert('No tienes privilegios de administrador');
          return;
        }
        setAdmin(data.user);
        setToken(data.token);
        localStorage.setItem('token', data.token);
        setShowLogin(false);
      } else {
        const errorData = await response.json();
        alert(errorData.detail || 'Error al iniciar sesión');
      }
    } catch (error) {
      alert('Error de conexión con el servidor');
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async () => {
    try {
      const response = await fetch(`${API_BASE}/products`);
      if (response.ok) {
        const productsData = await response.json();
        setProducts(productsData);
      }
    } catch (error) {
      console.error('Error loading products:', error);
    }
  };

  const handleLogout = () => {
    // Intentar hacer logout en el backend
    fetch(`${API_BASE}/admin/logout`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }).catch(console.error);
    
    // Limpiar frontend
    localStorage.removeItem('token');
    setAdmin(null);
    setToken(null);
    setShowLogin(true);
  };

  const handleSubmitProduct = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const productData = {
        ...formData,
        price: parseFloat(formData.price),
        stock: parseInt(formData.stock),
        requires_prescription: !!formData.requires_prescription,
        active: !!formData.active
      };

      // Si es edición, incluye el id en el body
      if (editingProduct) {
        productData.id = editingProduct.id;
      }

      const url = editingProduct 
        ? `${API_BASE}/admin/products/${editingProduct.id}`
        : `${API_BASE}/admin/products`;
      
      const method = editingProduct ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method: method,
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(productData)
      });

      if (response.ok) {
        alert(editingProduct ? '✅ Producto actualizado' : '✅ Producto creado');
        setShowProductModal(false);
        setEditingProduct(null);
        setFormData({
          name: '',
          description: '',
          price: '',
          category: '',
          stock: '',
          image_url: '',
          requires_prescription: false,
          active: true
        });
        loadProducts();
      } else {
        const errorData = await response.json();
        alert(errorData.detail || 'Error guardando producto');
      }
    } catch (error) {
      alert('Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteProduct = async (productId) => {
    if (!confirm('¿Estás seguro de eliminar este producto?')) return;

    try {
      const response = await fetch(`${API_BASE}/admin/products/${productId}`, {
        method: 'DELETE',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        alert('✅ Producto eliminado');
        loadProducts();
      } else {
        const errorData = await response.json();
        alert(errorData.detail || 'Error eliminando producto');
      }
    } catch (error) {
      alert('Error de conexión');
    }
  };

  const openEditModal = (product) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      description: product.description,
      price: product.price.toString(),
      category: product.category,
      stock: product.stock.toString(),
      image_url: product.image_url || '',
      requires_prescription: product.requires_prescription,
      active: product.active
    });
    setShowProductModal(true);
  };

  if (showLogin) {
    return (
      <div style={styles.adminLoginContainer}>
        <div style={styles.adminLoginForm}>
          <h2 style={{textAlign: 'center', marginBottom: '2rem', color: '#333'}}>
            🏥 Panel de Administración
          </h2>
          
          <form onSubmit={handleLogin}>
            <div style={styles.formGroup}>
              <label style={styles.label}>Email:</label>
              <input 
                type="email" 
                name="email"
                required 
                style={styles.input}
                placeholder="admin@farmachelo.com"
              />
            </div>
            
            <div style={styles.formGroup}>
              <label style={styles.label}>Contraseña:</label>
              <input 
                type="password" 
                name="password"
                required 
                style={styles.input}
                placeholder="admin123"
              />
            </div>
            
            <button 
              type="submit" 
              disabled={loading}
              style={{...styles.submitButton, opacity: loading ? 0.7 : 1}}
            >
              {loading ? '⏳ Iniciando sesión...' : '🚀 Iniciar Sesión'}
            </button>
          </form>
          <button 
            onClick={onBack}
            style={styles.backButton}
          >
            ↩️ Volver al Sitio Principal
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{padding: '20px', maxWidth: '1400px', margin: '0 auto', minHeight: '100vh'}}>
      {/* Header */}
      <div style={{
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '2rem',
        paddingBottom: '1rem',
        borderBottom: '2px solid #e5e7eb',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <h1 style={{color: '#333', margin: 0}}>
          🏥 Panel de Administración - Farmachelo
        </h1>
        
        <div style={{display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap'}}>
          <span style={{fontWeight: '600', color: '#4b5563'}}>
            👋 Bienvenido, {admin?.name}
          </span>
          
          <button 
            onClick={() => setShowProductModal(true)}
            style={{
              padding: '0.5rem 1rem', 
              background: '#10b981', 
              color: 'white', 
              border: 'none', 
              borderRadius: '6px', 
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            ➕ Nuevo Producto
          </button>
          
          <button 
            onClick={handleLogout}
            style={{
              padding: '0.5rem 1rem', 
              background: '#ef4444', 
              color: 'white', 
              border: 'none', 
              borderRadius: '6px', 
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            🚪 Cerrar Sesión
          </button>
          
          <button 
            onClick={onBack}
            style={{
              padding: '0.5rem 1rem', 
              background: '#6b7280', 
              color: 'white', 
              border: 'none', 
              borderRadius: '6px', 
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            ↩️ Volver al Sitio
          </button>
        </div>
      </div>

      {/* Products Section */}
      <div style={{
        background: 'white', 
        borderRadius: '12px', 
        padding: '2rem', 
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
        marginBottom: '2rem'
      }}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem'}}>
          <h2 style={{color: '#333', margin: 0}}>
            📦 Productos ({products.length})
          </h2>
        </div>
        
        {products.length === 0 ? (
          <p style={{textAlign: 'center', color: '#666', padding: '2rem'}}>
            No hay productos cargados en el sistema.
          </p>
        ) : (
          <div style={{overflowX: 'auto'}}>
            <table style={{width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem'}}>
              <thead>
                <tr style={{background: '#f8fafc'}}>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Imagen</th>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Nombre</th>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Precio</th>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Stock</th>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Categoría</th>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Estado</th>
                  <th style={{padding: '1rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb'}}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {products.map(product => (
                  <tr key={product.id}>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>
                      {product.image_url ? (
                        <img 
                          src={product.image_url} 
                          alt={product.name}
                          style={{width: '50px', height: '50px', objectFit: 'cover', borderRadius: '6px'}}
                        />
                      ) : (
                        <div style={{
                          width: '50px', 
                          height: '50px', 
                          background: '#f3f4f6', 
                          borderRadius: '6px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#9ca3af'
                        }}>
                          🏥
                        </div>
                      )}
                    </td>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>{product.name}</td>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>${product.price}</td>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>{product.stock}</td>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>
                      {product.category === 'prescription' ? '💊 Con receta' : '🟢 Sin receta'}
                    </td>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>
                      <span style={{
                        padding: '0.25rem 0.75rem',
                        borderRadius: '20px',
                        fontSize: '0.8rem',
                        fontWeight: '600',
                        background: product.active ? '#dcfce7' : '#fee2e2',
                        color: product.active ? '#166534' : '#991b1b'
                      }}>
                        {product.active ? '✅ Activo' : '❌ Inactivo'}
                      </span>
                    </td>
                    <td style={{padding: '1rem', borderBottom: '1px solid #e5e7eb'}}>
                      <button 
                        onClick={() => openEditModal(product)}
                        style={{
                          padding: '0.25rem 0.5rem', 
                          background: '#3b82f6', 
                          color: 'white', 
                          border: 'none', 
                          borderRadius: '4px', 
                              cursor: 'pointer',
                          marginRight: '0.5rem'
                        }}
                      >
                        ✏️ Editar
                      </button>
                      <button 
                        onClick={() => handleDeleteProduct(product.id)}
                        style={{
                          padding: '0.25rem 0.5rem', 
                          background: '#ef4444', 
                          color: 'white', 
                          border: 'none', 
                          borderRadius: '4px', 
                          cursor: 'pointer'
                        }}
                      >
                        🗑️ Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Product Modal */}
      {showProductModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            background: 'white',
            borderRadius: '12px',
            padding: '2rem',
            width: '100%',
            maxWidth: '600px',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h2 style={{marginBottom: '1.5rem', color: '#333'}}>
              {editingProduct ? '✏️ Editar Producto' : '➕ Nuevo Producto'}
            </h2>
            
            <form onSubmit={handleSubmitProduct}>
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem'}}>
                <div>
                  <label style={styles.label}>Nombre:</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                    style={styles.input}
                  />
                </div>
                <div>
                  <label style={styles.label}>Precio:</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.price}
                    onChange={(e) => setFormData({...formData, price: e.target.value})}
                    required
                    style={styles.input}
                  />
                </div>
              </div>

              <div style={{marginBottom: '1rem'}}>
                <label style={styles.label}>Descripción:</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  required
                  style={{...styles.input, minHeight: '80px'}}
                />
              </div>

              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem'}}>
                <div>
                  <label style={styles.label}>Categoría:</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({...formData, category: e.target.value})}
                    required
                    style={styles.input}
                  >
                    <option value="">Seleccionar categoría</option>
                    <option value="prescription">Con receta</option>
                    <option value="over_counter">Sin receta</option>
                  </select>
                </div>
                <div>
                  <label style={styles.label}>Stock:</label>
                  <input
                    type="number"
                    value={formData.stock}
                    onChange={(e) => setFormData({...formData, stock: e.target.value})}
                    required
                    style={styles.input}
                  />
                </div>
              </div>

              <div style={{marginBottom: '1rem'}}>
                <label style={styles.label}>URL de la imagen:</label>
                <input
                  type="url"
                  value={formData.image_url}
                  onChange={(e) => setFormData({...formData, image_url: e.target.value})}
                  style={styles.input}
                  placeholder="Opcional"
                />
              </div>

              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem'}}>
                <label style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                  <input
                    type="checkbox"
                    checked={formData.requires_prescription}
                    onChange={(e) => setFormData({...formData, requires_prescription: e.target.checked})}
                  />
                  Requiere receta
                </label>
                <label style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                  <input
                    type="checkbox"
                    checked={formData.active}
                    onChange={(e) => setFormData({...formData, active: e.target.checked})}
                  />
                  Producto activo
                </label>
              </div>

              <div style={{display: 'flex', gap: '1rem', justifyContent: 'flex-end'}}>
                <button
                  type="button"
                  onClick={() => {
                    setShowProductModal(false);
                    setEditingProduct(null);
                    setFormData({
                      name: '',
                      description: '',
                      price: '',
                      category: '',
                      stock: '',
                      image_url: '',
                      requires_prescription: false,
                      active: true
                    });
                  }}
                  style={{
                    padding: '0.75rem 1.5rem',
                    background: '#6b7280',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer'
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    padding: '0.75rem 1.5rem',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    opacity: loading ? 0.7 : 1
                  }}
                >
                  {loading ? '⏳ Guardando...' : (editingProduct ? '💾 Actualizar' : '✨ Crear')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;