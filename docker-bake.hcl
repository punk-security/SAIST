variable "VERSION" {

}

target "base" {
  context = "."
  dockerfile = "Dockerfile"
  platforms = ["linux/amd64", "linux/arm64"]
}

target "nightly" {
  inherits = ["base"]
  tags = ["docker.io/punksecurity/saist:nightly"]
  target = "saist"
}

target "release" {
  inherits = ["base"]
  tags = ["docker.io/punksecurity/saist:${VERSION}", "docker.io/punksecurity/saist:latest"]
  target = "saist"
}
