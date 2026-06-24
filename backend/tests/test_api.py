import pytest
from datetime import date
from fastapi import status

# Standard credentials configured in app.config
AUTH = ("admin", "travelsecret")
BAD_AUTH = ("admin", "wrongpassword")

# --- AUTHENTICATION TESTS ---

@pytest.mark.asyncio
async def test_auth_required(client):
    """Endpoints should require valid Basic Authentication."""
    # List projects without auth
    res = await client.get("/api/projects")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # List projects with bad auth
    res = await client.get("/api/projects", auth=BAD_AUTH)
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Health check is public
    res = await client.get("/health")
    assert res.status_code == status.HTTP_200_OK


# --- PROJECT CRUD TESTS ---

@pytest.mark.asyncio
async def test_project_crud(client):
    """Test standard project lifecycle (create, read, update, delete)."""
    # 1. Create project
    payload = {
        "name": "European Tour",
        "description": "Visiting capitals in Europe",
        "start_date": "2026-07-01"
    }
    res = await client.post("/api/projects", json=payload, auth=AUTH)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "European Tour"
    assert data["is_completed"] is False
    assert len(data["places"]) == 0
    project_id = data["id"]

    # 2. Get single project
    res = await client.get(f"/api/projects/{project_id}", auth=AUTH)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "European Tour"

    # 3. Update project details
    update_payload = {
        "name": "European Tour v2",
        "description": "Updated description",
        "start_date": "2026-08-01"
    }
    res = await client.put(f"/api/projects/{project_id}", json=update_payload, auth=AUTH)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["name"] == "European Tour v2"
    assert data["description"] == "Updated description"
    assert data["start_date"] == "2026-08-01"

    # 4. List projects
    res = await client.get("/api/projects", auth=AUTH)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 1

    # 5. Delete project
    res = await client.delete(f"/api/projects/{project_id}", auth=AUTH)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    # Verify deleted
    res = await client.get(f"/api/projects/{project_id}", auth=AUTH)
    assert res.status_code == status.HTTP_404_NOT_FOUND


# --- CREATE PROJECT WITH PLACES ---

@pytest.mark.asyncio
async def test_create_project_with_places(client):
    """Test single request creation of project with associated places."""
    payload = {
        "name": "Art Tour",
        "places": ["1001", "1002", "1003"]
    }
    res = await client.post("/api/projects/with-places", json=payload, auth=AUTH)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "Art Tour"
    assert len(data["places"]) == 3
    assert data["places"][0]["external_id"] == "1001"
    assert data["places"][0]["title"] == "Mock Artwork 1001"
    assert data["is_completed"] is False


@pytest.mark.asyncio
async def test_create_project_with_places_validation(client):
    """Test schema and API validations during creation with places."""
    # 1. Invalid external place ID
    payload = {
        "name": "Invalid Art Tour",
        "places": ["1001", "invalid"]
    }
    res = await client.post("/api/projects/with-places", json=payload, auth=AUTH)
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # 2. Too many places (>10)
    payload = {
        "name": "Overloaded Tour",
        "places": [str(i) for i in range(1, 12)]
    }
    res = await client.post("/api/projects/with-places", json=payload, auth=AUTH)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "between 1 and 10 places" in res.text

    # 3. Duplicate places in creation request
    payload = {
        "name": "Duplicate Tour",
        "places": ["1001", "1001"]
    }
    res = await client.post("/api/projects/with-places", json=payload, auth=AUTH)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "Duplicate external place IDs" in res.text

    # 4. Too few places (<1)
    payload = {
        "name": "Empty Tour",
        "places": []
    }
    res = await client.post("/api/projects/with-places", json=payload, auth=AUTH)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "at least 1 item" in res.text


# --- ADD PLACES & LIMITS ---

@pytest.mark.asyncio
async def test_add_place_to_existing_project(client):
    """Test adding places to an existing project and enforcing limits/uniqueness."""
    # Create empty project
    res = await client.post("/api/projects", json={"name": "Vacation"}, auth=AUTH)
    proj_id = res.json()["id"]

    # 1. Add valid place
    res = await client.post(f"/api/projects/{proj_id}/places", json={"external_id": "2001"}, auth=AUTH)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["external_id"] == "2001"
    assert res.json()["title"] == "Mock Artwork 2001"

    # 2. Add duplicate place (should fail)
    res = await client.post(f"/api/projects/{proj_id}/places", json={"external_id": "2001"}, auth=AUTH)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already added" in res.json()["detail"]

    # 3. Add invalid place (should fail 404)
    res = await client.post(f"/api/projects/{proj_id}/places", json={"external_id": "invalid"}, auth=AUTH)
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # 4. Fill project up to 10 places
    for idx in range(2, 11):
        res = await client.post(f"/api/projects/{proj_id}/places", json={"external_id": str(2000 + idx)}, auth=AUTH)
        assert res.status_code == status.HTTP_201_CREATED
    
    # 5. Try adding the 11th place (should fail 400)
    res = await client.post(f"/api/projects/{proj_id}/places", json={"external_id": "3000"}, auth=AUTH)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "maximum limit of 10 places" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_places_for_project(client):
    """Test retrieving all places and a single place within a project."""
    # Create a project with places
    payload = {
        "name": "Read Places Tour",
        "places": ["1001", "1002"]
    }
    res = await client.post("/api/projects/with-places", json=payload, auth=AUTH)
    proj_id = res.json()["id"]
    place1_id = res.json()["places"][0]["id"]

    # 1. List all places for the project
    res = await client.get(f"/api/projects/{proj_id}/places", auth=AUTH)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) == 2
    assert data[0]["external_id"] == "1001"
    assert data[1]["external_id"] == "1002"

    # 2. Get a single place within the project
    res = await client.get(f"/api/projects/{proj_id}/places/{place1_id}", auth=AUTH)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["external_id"] == "1001"
    assert res.json()["id"] == place1_id

    # 3. Try to get a non-existent place
    res = await client.get(f"/api/projects/{proj_id}/places/999999", auth=AUTH)
    assert res.status_code == status.HTTP_404_NOT_FOUND


# --- PLACE UPDATES & COMPLETENESS LOGIC ---

@pytest.mark.asyncio
async def test_completeness_and_deletion_rules(client):
    """
    Test calculations for project completion and rules prohibiting
    deletion of projects containing visited places.
    """
    # 1. Create a project with 2 places
    res = await client.post(
        "/api/projects/with-places",
        json={"name": "Dual Tour", "places": ["4001", "4002"]},
        auth=AUTH
    )
    proj = res.json()
    proj_id = proj["id"]
    place1 = proj["places"][0]
    place2 = proj["places"][1]

    assert proj["is_completed"] is False

    # 2. Update place 1 notes
    res = await client.patch(
        f"/api/projects/{proj_id}/places/{place1['id']}",
        json={"notes": "Must see painting"},
        auth=AUTH
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["notes"] == "Must see painting"
    assert res.json()["is_visited"] is False

    # 3. Mark place 1 as visited
    res = await client.patch(
        f"/api/projects/{proj_id}/places/{place1['id']}",
        json={"is_visited": True},
        auth=AUTH
    )
    assert res.json()["is_visited"] is True
    
    # Check project completeness - should still be False (place2 not visited yet)
    res = await client.get(f"/api/projects/{proj_id}", auth=AUTH)
    assert res.json()["is_completed"] is False

    # 4. Try deleting the project now (should fail because place1 is visited)
    res = await client.delete(f"/api/projects/{proj_id}", auth=AUTH)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "one or more places in this project have already been marked as visited" in res.json()["detail"]

    # 5. Mark place 2 as visited
    res = await client.patch(
        f"/api/projects/{proj_id}/places/{place2['id']}",
        json={"is_visited": True},
        auth=AUTH
    )
    assert res.json()["is_visited"] is True

    # Check project completeness - should now be True!
    res = await client.get(f"/api/projects/{proj_id}", auth=AUTH)
    assert res.json()["is_completed"] is True

    # 6. Add a new place to the completed project (should reset project completeness to False)
    res = await client.post(
        f"/api/projects/{proj_id}/places",
        json={"external_id": "4003"},
        auth=AUTH
    )
    assert res.status_code == status.HTTP_201_CREATED
    new_place = res.json()

    # Check completeness - should reset to False
    res = await client.get(f"/api/projects/{proj_id}", auth=AUTH)
    assert res.json()["is_completed"] is False

    # 7. Delete the new unvisited place
    res = await client.delete(
        f"/api/projects/{proj_id}/places/{new_place['id']}",
        auth=AUTH
    )
    assert res.status_code == status.HTTP_204_NO_CONTENT

    # Project completeness should recalculate and go back to True (only place1 and place2 remain, both visited)
    res = await client.get(f"/api/projects/{proj_id}", auth=AUTH)
    assert res.json()["is_completed"] is True
