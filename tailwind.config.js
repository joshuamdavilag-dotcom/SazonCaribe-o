/** Configuración de build de Tailwind (reemplaza el Play CDN en producción).
 *
 * Regenerar tras agregar clases nuevas en el ERP:
 *   npx tailwindcss@3.4.17 -c tailwind.config.js -i tailwind.input.css \
 *     -o app/Templates/css/tailwind.min.css --minify
 */
module.exports = {
  content: [
    './app/Templates/index.html',
    './app/Templates/js/app.js',
  ],
  theme: {
    extend: {
      screens: {
        xs: '400px',
      },
      fontFamily: {
        display: ['Epilogue', 'sans-serif'],
        sans: ['Plus Jakarta Sans', 'sans-serif'],
      },
      colors: {
        brand: {
          coral: '#C54320',
          coralHover: '#5B400C',
          coralLight: '#C54320',
          orange: '#C54320',
          navy: '#5B400C',
          navyDark: '#5B400C',
          navyDeep: '#5B400C',
          turquoise: '#006b33',
          turquoiseLight: '#006b33',
          sun: '#F1E246',
          sand: '#5B400C',
        },
      },
      boxShadow: {
        'card-tropical':
          '0 20px 40px -15px rgba(91, 64, 12, 0.45), 0 0 25px rgba(0, 107, 51, 0.24)',
        'btn-coral': '0 10px 20px -5px rgba(197, 67, 32, 0.45)',
      },
    },
  },
};
