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
          coralHover: '#A9381A',
          coralLight: '#FBEBE6',
          orange: '#D97A3A',
          navy: '#5b400C',
          navyDark: '#4A3409',
          navyDeep: '#3B2A07',
          turquoise: '#006b33',
          turquoiseLight: '#E6F2EB',
          sun: '#f1e246',
          sand: '#FBF6EA',
        },
      },
      boxShadow: {
        'card-tropical':
          '0 20px 40px -15px rgba(59, 42, 7, 0.45), 0 0 25px rgba(0, 107, 51, 0.12)',
        'btn-coral': '0 10px 20px -5px rgba(197, 67, 32, 0.45)',
      },
    },
  },
};
