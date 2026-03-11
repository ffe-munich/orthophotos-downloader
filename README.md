<br />
<div align="center">

<h3 align="center">orthophotos-downloader</h3>

  <p align="center">
    Python wrapper for various available WMS services to simplify the download of orthophotos. Currently focused on Germany.
    <br />
    <a href="https://github.com/ffe-munich/orthophotos-downloader"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    &middot;
    <a href="https://github.com/ffe-munich/orthophotos-downloader/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/ffe-munich/orthophotos-downloader/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

Orthophotos provide a high-precision data foundation for various applications in remote sensing – from environmental research to urban planning. However, Germany's federal structure means that each state has its own services and interfaces for providing this data, making nationwide usage cumbersome and complex.

With this software, we offer a central, user-friendly solution that allows users to download orthophotos independently of the respective state services. The software will support various data formats, including RGB and RGBI, and enable flexible geographical queries.


<p align="right">(<a href="#readme-top">back to top</a>)</p>




<!-- GETTING STARTED -->
## Getting Started


1. Clone the repo
   ```sh
   git clone https://github.com/ffe-munich/orthophotos-downloader.git
   ```
3. Setup a venv with python > 3.9
   ```sh
   python3.11 -m  venv "venv" 
   source venv/bin/activate
   ```
4. Pip install
   ```sh
   pip install .        
   ```


<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

You can find an example of usage in this [notebook](https://github.com/ffe-munich/orthophotos-downloader/examples/demo_bavaria_download.ipynb) in the examples folder

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- ROADMAP -->
## Roadmap

- [ ] Interface to give an area overlapping different wms services -> In Progress
- [ ] Command Line Interface
- [ ] Have a doc being generated
- [x] Integrate all WMS in germany
- [x] RGBI Download

See the [open issues](https://github.com/ffe-munich/orthophotos-downloader/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Coverage in Germany by Federal State (Bundesländer)

| Bundesland             | RGB | CIR |
|------------------------|:---:|:---:|
| Saarland               | ✅  | ✅  |
| Mecklenburg-Vorpommern | ✅  | ✅  |
| Rheinland-Pfalz        | ✅  | ✅  |
| Sachsen                | ✅  | ✅  |
| Thüringen              | ✅  | ✅  |
| Sachsen-Anhalt         | ✅  |     |
| Nordrhein-Westfalen    | ✅  | ✅  |
| Hessen                 | ✅  | ✅  |
| Hamburg                | ✅  | ✅  |
| Bremen                 | ✅  |     |
| Brandenburg            | ✅  | ✅  |
| Niedersachsen          | ✅  |     |
| Schleswig-Holstein     | ✅  |     |
| Bayern                 | ✅  | ✅  |
| Berlin                 | ✅  | ✅  |
| Baden-Württemberg      | ✅  | ✅  |




<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/ffe-munich/orthophotos-downloader">
  <img src="https://contrib.rocks/image?repo=ffe-munich/orthophotos-downloader" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## License

Distributed under Apache-2.0 license. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>





<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/ffe-munich/orthophotos-downloader.svg?style=for-the-badge
[contributors-url]: https://github.com/ffe-munich/orthophotos-downloader/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/ffe-munich/orthophotos-downloader.svg?style=for-the-badge
[forks-url]: https://github.com/ffe-munich/orthophotos-downloader/network/members
[stars-shield]: https://img.shields.io/github/stars/ffe-munich/orthophotos-downloader.svg?style=for-the-badge
[stars-url]: https://github.com/ffe-munich/orthophotos-downloader/stargazers
[issues-shield]: https://img.shields.io/github/issues/ffe-munich/orthophotos-downloader.svg?style=for-the-badge
[issues-url]: https://github.com/ffe-munich/orthophotos-downloader/issues
[license-shield]: https://img.shields.io/github/license/ffe-munich/orthophotos-downloader.svg?style=for-the-badge
[license-url]: https://github.com/ffe-munich/orthophotos-downloader/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 