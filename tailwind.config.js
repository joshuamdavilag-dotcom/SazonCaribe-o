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
          coralHover: '#A9331B',
          coralLight: '#FCEBE6',
          orange: '#C54320',
          navy: '#0F3B66',
          navyDark: '#0D233A',
          navyDeep: '#081726',
          turquoise: '#006b33',
          turquoiseLight: '#E8F3EC',
          sun: '#F1E246',
          sand: '#FBF8F3',
        },
      },
      boxShadow: {
        'card-tropical':
          '0 20px 40px -15px rgba(8, 23, 38, 0.45), 0 0 25px rgba(0, 107, 51, 0.12)',
        'btn-coral': '0 10px 20px -5px rgba(197, 67, 32, 0.45)',
      },
    },
  },
};
