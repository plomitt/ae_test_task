document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('weatherForm');
    const submitBtn = document.getElementById('submitBtn');
    const loading = document.getElementById('loading');
    const output = document.getElementById('output');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Get form values
        const formData = new FormData(form);
        const params = new URLSearchParams();

        // Get location type
        const locationType = formData.get('locationType');

        // Get location parameters based on type
        if (locationType === 'coordinates') {
            const lat = formData.get('lat');
            const lon = formData.get('lon');

            // Allow empty coordinates - backend will use defaults
            if (lat) params.append('lat', lat);
            if (lon) params.append('lon', lon);
        } else {
            const city = formData.get('city');

            // Allow empty city - backend will use defaults
            if (city && city.trim()) {
                params.append('city', city.trim());
            }
        }

        // Add timezone option
        const timezoneOption = formData.get('timezoneOption');
        params.append('timezone_option', timezoneOption);

        // Show loading
        loading.style.display = 'block';
        submitBtn.disabled = true;
        output.innerHTML = '';

        try {
            // Make API request
            const response = await fetch(`/weather/?${params.toString()}`);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            displayForecast(data);

        } catch (error) {
            displayError(error.message);
        } finally {
            // Hide loading
            loading.style.display = 'none';
            submitBtn.disabled = false;
        }
    });

    function displayForecast(data) {
        let html = `<h3>Weather for ${data.location.city || 'Location'}</h3>`;
        html += `<p>Coordinates: ${data.location.lat}, ${data.location.lon}</p>`;
        html += `<p>Timezone: ${data.timezone}</p>`;

        if (data.forecast && data.forecast.length > 0) {
            html += '<h4>Forecast:</h4>';
            data.forecast.forEach(item => {
                html += `
                    <div class="forecast-item">
                        <strong>${item.date} ${item.time}</strong><br>
                        Temperature: ${item.temperature_c}°C
                    </div>
                `;
            });
        } else {
            html += '<p>No forecast data available</p>';
        }

        output.innerHTML = html;
    }

    function displayError(message) {
        output.innerHTML = `<p class="error">Error: ${message}</p>`;
    }
});