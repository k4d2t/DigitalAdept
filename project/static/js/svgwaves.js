function setSVGwaves() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const svg = isDark ?
    `<svg width="100%" height="100%" viewBox="0 0 1440 900" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
    <defs>
    <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#223355"/>
    <stop offset="100%" stop-color="#17264a"/>
    </linearGradient>
    <linearGradient id="g2" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0%" stop-color="#4fc3f7" stop-opacity="0.13"/>
    <stop offset="100%" stop-color="#1976d2" stop-opacity="0.18"/>
    </linearGradient>
    <linearGradient id="g3" x1="0" y1="0.5" x2="1" y2="0.5">
    <stop offset="0%" stop-color="#4fc3f7" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="#1976d2" stop-opacity="0.1"/>
    </linearGradient>
    </defs>
    <rect width="1440" height="900" fill="url(#g1)"/>
    <path d="M0 670 Q360 720 720 600 T1440 670 V900 H0 Z" fill="url(#g2)">
    <animate attributeName="d" dur="7s" repeatCount="indefinite"
    values="
    M0 670 Q360 720 720 600 T1440 670 V900 H0 Z;
    M0 650 Q360 750 720 620 T1440 690 V900 H0 Z;
    M0 700 Q360 710 720 660 T1440 700 V900 H0 Z;
    M0 670 Q360 720 720 600 T1440 670 V900 H0 Z
    "/>
    </path>
    <path d="M0 800 Q380 850 900 680 T1440 820 V900 H0 Z" fill="url(#g3)">
    <animate attributeName="d" dur="10s" repeatCount="indefinite"
    values="
    M0 800 Q380 850 900 680 T1440 820 V900 H0 Z;
    M0 820 Q380 830 900 700 T1440 800 V900 H0 Z;
    M0 790 Q380 870 900 700 T1440 830 V900 H0 Z;
    M0 800 Q380 850 900 680 T1440 820 V900 H0 Z
    "/>
    </path>
    </svg>`
    :
    `<svg width="100%" height="100%" viewBox="0 0 1440 900" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
    <defs>
    <linearGradient id="g1l" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#e3f6ff"/>
    <stop offset="100%" stop-color="#b8e2fa"/>
    </linearGradient>
    <linearGradient id="g2l" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0%" stop-color="#4fc3f7" stop-opacity="0.10"/>
    <stop offset="100%" stop-color="#1976d2" stop-opacity="0.13"/>
    </linearGradient>
    <linearGradient id="g3l" x1="0" y1="0.5" x2="1" y2="0.5">
    <stop offset="0%" stop-color="#4fc3f7" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="#1976d2" stop-opacity="0.09"/>
    </linearGradient>
    </defs>
    <rect width="1440" height="900" fill="url(#g1l)"/>
    <path d="M0 670 Q360 720 720 600 T1440 670 V900 H0 Z" fill="url(#g2l)">
    <animate attributeName="d" dur="7s" repeatCount="indefinite"
    values="
    M0 670 Q360 720 720 600 T1440 670 V900 H0 Z;
    M0 650 Q360 750 720 620 T1440 690 V900 H0 Z;
    M0 700 Q360 710 720 660 T1440 700 V900 H0 Z;
    M0 670 Q360 720 720 600 T1440 670 V900 H0 Z
    "/>
    </path>
    <path d="M0 800 Q380 850 900 680 T1440 820 V900 H0 Z" fill="url(#g3l)">
    <animate attributeName="d" dur="10s" repeatCount="indefinite"
    values="
    M0 800 Q380 850 900 680 T1440 820 V900 H0 Z;
    M0 820 Q380 830 900 700 T1440 800 V900 H0 Z;
    M0 790 Q380 870 900 700 T1440 830 V900 H0 Z;
    M0 800 Q380 850 900 680 T1440 820 V900 H0 Z
    "/>
    </path>
    </svg>`;
    document.getElementById('svg-bg').innerHTML = svg;
}
window.addEventListener('DOMContentLoaded', setSVGwaves);
window.addEventListener('storage', setSVGwaves);
document.addEventListener('themechange', setSVGwaves);
