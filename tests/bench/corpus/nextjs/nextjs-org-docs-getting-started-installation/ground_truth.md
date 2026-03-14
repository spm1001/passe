# Installation

Create a new Next.js app and run it locally.

## Quick start

- Create a new Next.js app named
`my-app`

`cd my-app`

and start the dev server.- Visit
`http://localhost:3000`

.

```
pnpm create next-app@latest my-app --yes
cd my-app
pnpm dev
```


`--yes`

skips prompts using saved preferences or defaults. The default setup enables TypeScript, Tailwind, ESLint, App Router, and Turbopack, with import alias`@/*`

.

## System requirements

Before you begin, make sure your development environment meets the following requirements:

- Minimum Node.js version:
[20.9](https://nodejs.org/) - Operating systems: macOS, Windows (including WSL), and Linux.

## Supported browsers

Next.js supports modern browsers with zero configuration.

- Chrome 111+
- Edge 111+
- Firefox 111+
- Safari 16.4+

Learn more about [browser support](https://nextjs.org/docs/architecture/supported-browsers), including how to configure polyfills and target specific browsers.

## Create with the CLI

The quickest way to create a new Next.js app is using [ create-next-app](https://nextjs.org/docs/app/api-reference/cli/create-next-app), which sets up everything automatically for you. To create a project, run:

`pnpm create next-app`


On installation, you'll see the following prompts:

```
What is your project named? my-app
Would you like to use the recommended Next.js defaults?
Yes, use recommended defaults - TypeScript, ESLint, Tailwind CSS, App Router, Turbopack
No, reuse previous settings
No, customize settings - Choose your own preferences
```


If you choose to `customize settings`

, you'll see the following prompts:

```
Would you like to use TypeScript? No / Yes
Which linter would you like to use? ESLint / Biome / None
Would you like to use React Compiler? No / Yes
Would you like to use Tailwind CSS? No / Yes
Would you like your code inside a `src/` directory? No / Yes
Would you like to use App Router? (recommended) No / Yes
Would you like to customize the import alias (`@/*` by default)? No / Yes
What import alias would you like configured? @/*
```


After the prompts, [ create-next-app](https://nextjs.org/docs/app/api-reference/cli/create-next-app) will create a folder with your project name and install the required dependencies.

## Manual installation

To manually create a new Next.js app, install the required packages:

`pnpm i next@latest react@latest react-dom@latest`



Good to know:

- The
`App Router`

uses[React canary releases]built-in, which include all the stable React 19 changes, as well as newer features being validated in frameworks, but you should still declare react and react-dom in package.json for tooling and ecosystem compatibility.- The
`Pages Router`

uses the React version from your`package.json`

.

Then, add the following scripts to your `package.json`

file:

```
{
"scripts": {
"dev": "next dev",
"build": "next build",
"start": "next start",
"lint": "eslint",
"lint:fix": "eslint --fix"
}
}
```


These scripts refer to the different stages of developing an application:

`next dev`

: Starts the development server using Turbopack (default bundler).`next build`

: Builds the application for production.`next start`

: Starts the production server.`eslint`

: Runs ESLint.

Turbopack is now the default bundler. To use Webpack run `next dev --webpack`

or `next build --webpack`

. See the [Turbopack docs](https://nextjs.org/docs/app/api-reference/turbopack) for configuration details.

### Create the `app`

directory

Next.js uses file-system routing, which means the routes in your application are determined by how you structure your files.

Create an `app`

folder. Then, inside `app`

, create a `layout.tsx`

file. This file is the [root layout](https://nextjs.org/docs/app/api-reference/file-conventions/layout#root-layout). It's required and must contain the ` and `

` tags.`


```
export default function RootLayout({
children,
}: {
children: React.ReactNode
}) {
return (
<html lang="en">
<body>{children}body>
html>
)
}
```


Create a home page `app/page.tsx`

with some initial content:

```
export default function Page() {
return <h1>Hello, Next.js!h1>
}
```


Both `layout.tsx`

and `page.tsx`

will be rendered when the user visits the root of your application (`/`

).


Good to know:

- If you forget to create the root layout, Next.js will automatically create this file when running the development server with
`next dev`

.- You can optionally use a
[in the root of your project to separate your application's code from configuration files.]`src`

folder

### Create the `public`

folder (optional)

Create a [ public folder](https://nextjs.org/docs/app/api-reference/file-conventions/public-folder) at the root of your project to store static assets such as images, fonts, etc. Files inside

`public`

can then be referenced by your code starting from the base URL (`/`

).You can then reference these assets using the root path (`/`

). For example, `public/profile.png`

can be referenced as `/profile.png`

:

```
import Image from 'next/image'
export default function Page() {
return <Image src="/profile.png" alt="Profile" width={100} height={100} />
}
```


## Run the development server

- Run
`npm run dev`

to start the development server. - Visit
`http://localhost:3000`

to view your application. - Edit the
`app/page.tsx`

file and save it to see the updated result in your browser.

## Set up TypeScript

Minimum TypeScript version:

`v5.1.0`


Next.js comes with built-in TypeScript support. To add TypeScript to your project, rename a file to `.ts`

/ `.tsx`

and run `next dev`

. Next.js will automatically install the necessary dependencies and add a `tsconfig.json`

file with the recommended config options.

### IDE Plugin

Next.js includes a custom TypeScript plugin and type checker, which VSCode and other code editors can use for advanced type-checking and auto-completion.

You can enable the plugin in VS Code by:

- Opening the command palette (
`Ctrl/⌘`

+`Shift`

+`P`

) - Searching for "TypeScript: Select TypeScript Version"
- Selecting "Use Workspace Version"

See the [TypeScript reference](https://nextjs.org/docs/app/api-reference/config/typescript) page for more information.

## Set up linting

Next.js supports linting with either ESLint or Biome. Choose a linter and run it directly via `package.json`

scripts.

- Use
**ESLint**(comprehensive rules):

```
{
"scripts": {
"lint": "eslint",
"lint:fix": "eslint --fix"
}
}
```


- Or use
**Biome**(fast linter + formatter):

```
{
"scripts": {
"lint": "biome check",
"format": "biome format --write"
}
}
```


If your project previously used `next lint`

, migrate your scripts to the ESLint CLI with the codemod:

`npx @next/codemod@canary next-lint-to-eslint-cli .`


If you use ESLint, create an explicit config (recommended `eslint.config.mjs`

). ESLint supports both [the legacy .eslintrc.* and the newer eslint.config.mjs formats](https://eslint.org/docs/latest/use/configure/configuration-files#configuring-eslint). See the


[ESLint API reference](https://nextjs.org/docs/app/api-reference/config/eslint#with-core-web-vitals)for a recommended setup.


Good to know: Starting with Next.js 16,`next build`

no longer runs the linter automatically. Instead, you can run your linter through NPM scripts.

See the [ESLint Plugin](https://nextjs.org/docs/app/api-reference/config/eslint) page for more information.

## Set up Absolute Imports and Module Path Aliases

Next.js has in-built support for the `"paths"`

and `"baseUrl"`

options of `tsconfig.json`

and `jsconfig.json`

files.

These options allow you to alias project directories to absolute paths, making it easier and cleaner to import modules. For example:

```
// Before
import { Button } from '../../../components/button'
// After
import { Button } from '@/components/button'
```


To configure absolute imports, add the `baseUrl`

configuration option to your `tsconfig.json`

or `jsconfig.json`

file. For example:

```
{
"compilerOptions": {
"baseUrl": "src/"
}
}
```


In addition to configuring the `baseUrl`

path, you can use the `"paths"`

option to `"alias"`

module paths.

For example, the following configuration maps `@/components/*`

to `components/*`

:

```
{
"compilerOptions": {
"baseUrl": "src/",
"paths": {
"@/styles/*": ["styles/*"],
"@/components/*": ["components/*"]
}
}
}
```


Each of the `"paths"`

are relative to the `baseUrl`

location.

Was this helpful?