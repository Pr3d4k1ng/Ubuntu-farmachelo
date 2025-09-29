import React, { useState } from 'react';
import ProductCard from './ProductCard';

const ProductCatalog = ({ products, onAddToCart, user }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || product.category === selectedCategory;
    return matchesSearch && matchesCategory && product.active;
  });

  const categories = [
    { value: 'all', label: 'Todos los productos' },
    { value: 'prescription', label: 'Con receta' },
    { value: 'over_counter', label: 'Sin receta' }
  ];

  return (
    <section id="productos" className="product-catalog">
      <div className="container">
        <h2 className="section-title">Nuestros Productos</h2>
        
        {/* Filtros */}
        <div className="catalog-filters">
          <div className="search-box">
            <input
              type="text"
              placeholder="Buscar productos..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
            <span className="search-icon">🔍</span>
          </div>
          
          <div className="category-filter">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="category-select"
            >
              {categories.map(category => (
                <option key={category.value} value={category.value}>
                  {category.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Grid de productos */}
        <div className="products-grid">
          {filteredProducts.length === 0 ? (
            <div className="no-products">
              <p>No se encontraron productos con los filtros seleccionados.</p>
            </div>
          ) : (
            filteredProducts.map(product => (
              <ProductCard
                key={product.id}
                product={product}
                onAddToCart={onAddToCart}
                user={user}
              />
            ))
          )}
        </div>
      </div>
    </section>
  );
};

export default ProductCatalog;
