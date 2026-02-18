# Kevin Douglas Delong - Software Engineer Portfolio

A professional portfolio website showcasing web, mobile, and desktop applications with interactive demos.

## 🚀 Tech Stack

- **Static Site Generator:** Hugo v0.134.0 (Extended)
- **Theme:** Ananke
- **Deployment:** Netlify
- **Embedded Apps:** React-based games and interactive demos

## 📋 Features

- **About Me:** Professional introduction and key skills
- **Projects:** Interactive embedded applications including:
  - Scientific Calculator
  - Tic Tac Toe Game
  - Blackjack Game
  - Ride-Sharing Entertainment Center
  - Circle Clicker
  - Color Match Game
- **Resume:** Downloadable resume and cover letter
- **Contact:** Professional contact information
- **Donate:** Support page with Venmo integration

## 🛠️ Local Development

### Prerequisites

- Hugo Extended v0.134.0 or later
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/delongkevin/2025-Portfolio-SoftwareEngineer.git
cd 2025-Portfolio-SoftwareEngineer
```

2. Initialize the theme submodule:
```bash
git submodule update --init --recursive
```

3. Run the development server:
```bash
hugo server
```

4. Open your browser to `http://localhost:1313`

### Building for Production

```bash
hugo --gc --minify
```

The built site will be in the `public/` directory.

## 📁 Project Structure

```
.
├── content/              # Markdown content files
├── layouts/              # Hugo layout templates
│   └── shortcodes/      # Custom shortcodes for embedded games
├── static/              # Static assets (CSS, JS, images, games)
│   ├── calculator/      # Scientific calculator app
│   ├── space-shooter/   # Space shooter game
│   ├── css/            # Custom stylesheets
│   ├── images/         # Images and media
│   └── resume/         # Resume documents
├── themes/              # Hugo themes
│   └── ananke/         # Ananke theme (submodule)
├── hugo.toml           # Hugo configuration
├── netlify.toml        # Netlify deployment config
└── .gitignore          # Git ignore rules
```

## 🌐 Deployment

This site is configured for automatic deployment on Netlify:

- **Build Command:** `hugo --gc --minify`
- **Publish Directory:** `public`
- **Hugo Version:** 0.134.0

## 📝 Adding New Projects

1. Add your game/app build files to `static/your-app-name/`
2. Create a shortcode in `layouts/shortcodes/your-app-name.html`
3. Reference it in `content/projects.md` using `{{< your-app-name >}}`

## 🔒 Security

- SSH keys and credentials are excluded via `.gitignore`
- Build artifacts are not committed to the repository
- Sensitive configuration files are ignored

## 📧 Contact

- **Email:** delong.kevin@gmail.com
- **LinkedIn:** [kevin-delong](https://www.linkedin.com/in/kevin-delong-50726135b/)
- **GitHub:** [@delongkevin](https://github.com/delongkevin)

## 📄 License

© 2026 Kevin Douglas Delong. All rights reserved.
